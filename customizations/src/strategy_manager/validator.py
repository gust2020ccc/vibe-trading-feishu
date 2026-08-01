"""AST-based source code validation for strategies and factors.

Reuses the security validation logic from ``backtest.runner`` but operates
on **source strings** (from the DB) instead of file paths.  This module is
the single entry point for all code-safety checks before persisting user
strategy or factor source code.

Validation layers
-----------------
1. **Syntax** — ``ast.parse()`` must succeed.
2. **Structural (import-time)** — no decorators, no executable top-level
   statements, no unsafe annotations / base classes.  Mirrors
   ``_validate_signal_engine_source`` from ``backtest.runner``.
3. **Runtime-reachable scrub** — walks every ``SignalEngine`` method (and
   their transitive callees) rejecting network / process-spawn / dynamic-exec
   / filesystem-write operations.  Mirrors ``_scan_runtime_reachable``.
4. **Metadata extraction** — parses ``__init__`` defaults so the Web UI can
   render parameter controls (reuses logic from ``templates.py``).

The internal helper functions intentionally replicate the runner's private
implementations (``_validate_function_def``, ``_reject_forbidden_node`` …)
because the runner only exposes a *file-path* API and keeping a thin source-
string wrapper around temp files is fragile across platforms.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class ValidationResult:
    """Outcome of validating a piece of source code."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def error_message(self) -> str:
        """First error message, or empty string."""
        return self.errors[0] if self.errors else ""


# --------------------------------------------------------------------------- #
# Forbidden sets (kept in sync with backtest.runner)
# --------------------------------------------------------------------------- #
_FORBIDDEN_IMPORT_MODULES = frozenset(
    {
        "socket",
        "socketserver",
        "subprocess",
        "urllib",
        "urllib2",
        "urllib3",
        "http",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "telnetlib",
        "multiprocessing",
        "ctypes",
    }
)

_FORBIDDEN_OS_ATTRS = frozenset(
    {
        "system",
        "popen",
        "popen2",
        "popen3",
        "popen4",
        "fork",
        "forkpty",
        "putenv",
        "unsetenv",
        "getenv",
        "environ",
        "environb",
        "startfile",
    }
)

_FORBIDDEN_BUILTINS = frozenset(
    {"eval", "exec", "compile", "__import__", "globals", "locals", "vars", "breakpoint"}
)

_GETATTR_INDIRECTION = frozenset({"getattr", "setattr", "delattr"})
_OPEN_WRITE_MODE_CHARS = frozenset("wax+")
_SCRUB_MSG = "is not allowed inside generated strategy code"


# --------------------------------------------------------------------------- #
# Structural helpers (import-time checks)
# --------------------------------------------------------------------------- #
def _is_literal_node(node: ast.AST) -> bool:
    """Return whether an AST node is made only from literal values."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_literal_node(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_literal_node(key)) and _is_literal_node(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _is_safe_constant_assignment(node: ast.AST) -> bool:
    """Return whether a top-level assignment is literal-only."""
    if isinstance(node, ast.Assign):
        return _is_literal_node(node.value)
    if isinstance(node, ast.AnnAssign):
        return node.value is None or _is_literal_node(node.value)
    return False


def _is_safe_reference(node: ast.AST | None) -> bool:
    """Return whether an annotation/base expression cannot call code."""
    if node is None:
        return True
    if isinstance(node, (ast.Name, ast.Attribute, ast.Constant)):
        return True
    if isinstance(node, ast.Subscript):
        return _is_safe_reference(node.value) and _is_safe_reference(node.slice)
    if isinstance(node, ast.Tuple):
        return all(_is_safe_reference(item) for item in node.elts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_safe_reference(node.left) and _is_safe_reference(node.right)
    return False


def _validate_function_def(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return list of errors found in a function definition."""
    errors: list[str] = []
    if node.decorator_list:
        errors.append(f"Decorators are not allowed on function {node.name!r}")
    for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
        if not _is_literal_node(default):
            errors.append(f"Non-literal default is not allowed on function {node.name!r}")
    annotations = [node.returns]
    annotations.extend(arg.annotation for arg in node.args.posonlyargs)
    annotations.extend(arg.annotation for arg in node.args.args)
    annotations.extend(arg.annotation for arg in node.args.kwonlyargs)
    annotations.append(node.args.vararg.annotation if node.args.vararg else None)
    annotations.append(node.args.kwarg.annotation if node.args.kwarg else None)
    for annotation in annotations:
        if not _is_safe_reference(annotation):
            errors.append(f"Unsafe annotation is not allowed on function {node.name!r}")
    return errors


def _validate_class_body(node: ast.ClassDef) -> list[str]:
    """Return list of errors found in a class body."""
    errors: list[str] = []
    if node.decorator_list:
        errors.append(f"Decorators are not allowed on class {node.name!r}")
    for base in node.bases:
        if not _is_safe_reference(base):
            errors.append(f"Unsafe base class is not allowed on class {node.name!r}")
    if node.keywords:
        errors.append(f"Class keywords are not allowed on class {node.name!r}")
    for child in node.body:
        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(_validate_function_def(child))
            continue
        if _is_safe_constant_assignment(child):
            continue
        if isinstance(child, ast.Pass):
            continue
        errors.append(
            f"Executable class-level statement {type(child).__name__} is not allowed"
        )
    return errors


# --------------------------------------------------------------------------- #
# Runtime-reachable scrubber
# --------------------------------------------------------------------------- #
def _is_forbidden_os_attr(attr: str) -> bool:
    """Return whether ``os.<attr>`` shells out, spawns, execs, or reads env."""
    return attr in _FORBIDDEN_OS_ATTRS or attr.startswith(("spawn", "exec"))


def _attribute_root_name(node: ast.Attribute) -> str | None:
    """Return the leftmost ``Name`` id of an attribute chain (``a.b.c`` -> ``a``)."""
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _reject_forbidden_open(node: ast.Call) -> str | None:
    """Return error message if ``open()`` writes files or reads unsafe path."""
    func = node.func
    is_builtin_open = isinstance(func, ast.Name) and func.id == "open"
    is_io_os_open = (
        isinstance(func, ast.Attribute)
        and func.attr == "open"
        and isinstance(func.value, ast.Name)
        and func.value.id in {"io", "os"}
    )
    if not (is_builtin_open or is_io_os_open):
        return None

    mode_node: ast.AST | None = node.args[1] if len(node.args) >= 2 else None
    for kw in node.keywords:
        if kw.arg == "mode":
            mode_node = kw.value
    if mode_node is not None:
        if not (isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str)):
            return f"open() with a non-literal mode {_SCRUB_MSG}"
        if any(ch in _OPEN_WRITE_MODE_CHARS for ch in mode_node.value):
            return f"Writing files via open(mode={mode_node.value!r}) {_SCRUB_MSG}"

    path_node = node.args[0] if node.args else None
    if not (isinstance(path_node, ast.Constant) and isinstance(path_node.value, str)):
        return f"open() with a non-literal path {_SCRUB_MSG}"
    path = path_node.value
    if path.startswith(("/", "~", "\\")) or ".." in path or (len(path) > 1 and path[1] == ":"):
        return f"open() with a non-relative path {path!r} {_SCRUB_MSG}"
    return None


def _reject_forbidden_getattr(node: ast.Call) -> str | None:
    """Return error message if getattr/setattr/delattr indirection onto os/forbidden."""
    func = node.func
    if not (isinstance(func, ast.Name) and func.id in _GETATTR_INDIRECTION):
        return None
    if not node.args:
        return None
    target = node.args[0]
    if isinstance(target, ast.Name):
        root: str | None = target.id
    elif isinstance(target, ast.Attribute):
        root = _attribute_root_name(target)
    else:
        root = None
    if root == "os" or root in _FORBIDDEN_IMPORT_MODULES:
        return f"{func.id}() indirection onto {root!r} {_SCRUB_MSG}"
    return None


def _check_forbidden_node(node: ast.AST) -> str | None:
    """Return error message if a single AST node performs a forbidden operation."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] in _FORBIDDEN_IMPORT_MODULES:
                return f"Import of {alias.name!r} {_SCRUB_MSG}"
    elif isinstance(node, ast.ImportFrom):
        root = (node.module or "").split(".")[0]
        if root in _FORBIDDEN_IMPORT_MODULES:
            return f"Import from {node.module!r} {_SCRUB_MSG}"
        if root == "os":
            for alias in node.names:
                if _is_forbidden_os_attr(alias.name):
                    return f"Import of os.{alias.name} {_SCRUB_MSG}"
    elif isinstance(node, ast.Attribute):
        root = _attribute_root_name(node)
        if root in _FORBIDDEN_IMPORT_MODULES:
            return f"Use of {root}.{node.attr} {_SCRUB_MSG}"
        if root == "os" and _is_forbidden_os_attr(node.attr):
            return f"Use of os.{node.attr} {_SCRUB_MSG}"
    elif isinstance(node, ast.Name):
        if node.id in _FORBIDDEN_BUILTINS:
            return f"Use of {node.id!r} {_SCRUB_MSG}"
    elif isinstance(node, ast.Call):
        msg = _reject_forbidden_open(node)
        if msg:
            return msg
        msg = _reject_forbidden_getattr(node)
        if msg:
            return msg
    return None


def _scan_runtime_reachable(tree: ast.Module) -> list[str]:
    """Scan SignalEngine methods + transitive callees for forbidden operations.

    Returns a list of error messages (empty if clean).
    """
    errors: list[str] = []
    engine_cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SignalEngine"),
        None,
    )
    if engine_cls is None:
        # No SignalEngine class — for factors this is fine, for strategies it's an error
        return errors

    module_funcs = {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    worklist: list[ast.AST] = [
        m for m in engine_cls.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    visited: set[int] = set()
    while worklist:
        fn = worklist.pop()
        if id(fn) in visited:
            continue
        visited.add(id(fn))
        for node in ast.walk(fn):
            msg = _check_forbidden_node(node)
            if msg:
                errors.append(msg)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                target = module_funcs.get(node.func.id)
                if target is not None:
                    worklist.append(target)
    return errors


# --------------------------------------------------------------------------- #
# Top-level structural validation
# --------------------------------------------------------------------------- #
def _validate_structure(tree: ast.Module) -> list[str]:
    """Validate import-time safety of the module (mirrors runner logic)."""
    errors: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "signal_engine":
            errors.append(
                "Circular import: 'from signal_engine import ...' imports the file from itself."
            )
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Check for forbidden modules (subprocess, socket, http, etc.)
            msg = _check_forbidden_node(node)
            if msg:
                errors.append(msg)
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(_validate_function_def(node))
            continue
        if isinstance(node, ast.ClassDef):
            errors.extend(_validate_class_body(node))
            continue
        if _is_safe_constant_assignment(node):
            continue
        errors.append(
            f"Executable top-level statement {type(node).__name__} is not allowed"
        )
    return errors


# --------------------------------------------------------------------------- #
# Metadata extraction
# --------------------------------------------------------------------------- #
def _extract_param_type_and_default(default_node: ast.AST) -> tuple[str, Any]:
    """Infer parameter type and default value from an AST default node.

    Returns ``(type_str, default_value)``.
    """
    if isinstance(default_node, ast.Constant):
        val = default_node.value
        if isinstance(val, bool):
            return ("bool", val)
        if isinstance(val, int):
            return ("int", val)
        if isinstance(val, float):
            return ("float", val)
        if isinstance(val, str):
            return ("str", val)
        return ("str", str(val))
    if isinstance(default_node, ast.UnaryOp):
        try:
            val = ast.literal_eval(default_node)
            if isinstance(val, float):
                return ("float", val)
            return ("int", val)
        except Exception:  # noqa: BLE001
            return ("str", "")
    if isinstance(default_node, ast.List):
        try:
            val = ast.literal_eval(default_node)
            return ("list", val)
        except Exception:  # noqa: BLE001
            return ("list", [])
    if isinstance(default_node, ast.Tuple):
        try:
            val = ast.literal_eval(default_node)
            return ("list", list(val))
        except Exception:  # noqa: BLE001
            return ("list", [])
    return ("str", "")


def extract_strategy_metadata(source: str) -> dict[str, Any]:
    """Extract metadata from a ``signal_engine.py`` source string.

    Parses:
      - Module docstring → ``description``
      - ``SignalEngine.__init__`` parameters → ``parameters`` list
      - Class docstring → ``class_description``

    Returns a dict with keys ``description``, ``parameters``, ``class_description``.
    On any parse error returns a minimal dict.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"description": "", "parameters": [], "class_description": ""}

    # Module docstring
    description = ""
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        doc = tree.body[0].value.value.strip()
        description = doc.split("\n")[0][:200]

    parameters: list[dict[str, Any]] = []
    class_description = ""

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "SignalEngine"):
            continue

        # Class docstring
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            class_description = node.body[0].value.value.strip()

        for item in node.body:
            if not (isinstance(item, ast.FunctionDef) and item.name == "__init__"):
                continue
            args = item.args
            defaults_offset = len(args.args) - len(args.defaults)
            for i, arg in enumerate(args.args):
                if i == 0:  # skip self
                    continue
                param: dict[str, Any] = {
                    "key": arg.arg,
                    "label": arg.arg,
                    "type": "str",
                    "default": "",
                    "required": True,
                }
                default_idx = i - defaults_offset
                if 0 <= default_idx < len(args.defaults):
                    ptype, pdefault = _extract_param_type_and_default(args.defaults[default_idx])
                    param["type"] = ptype
                    param["default"] = pdefault
                    param["required"] = False
                parameters.append(param)
            break
        break

    return {
        "description": description,
        "parameters": parameters,
        "class_description": class_description,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def validate_strategy_source(source: str) -> ValidationResult:
    """Validate a strategy ``signal_engine.py`` source string.

    Performs:
      1. Syntax check
      2. Structural (import-time) safety check
      3. Runtime-reachable operation scrub
      4. Required: ``SignalEngine`` class with ``generate`` method
      5. Metadata extraction

    Returns a :class:`ValidationResult`.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Syntax
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ValidationResult(
            valid=False,
            errors=[f"Syntax error: {exc}"],
        )

    # 2. Structural (import-time)
    errors.extend(_validate_structure(tree))

    # 3. Runtime-reachable scrub
    errors.extend(_scan_runtime_reachable(tree))

    # 4. Required structure: SignalEngine class
    has_signal_engine = any(
        isinstance(n, ast.ClassDef) and n.name == "SignalEngine"
        for n in tree.body
    )
    if not has_signal_engine:
        errors.append("Missing required class 'SignalEngine'")
    else:
        # Check for generate method
        engine_cls = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SignalEngine"
        )
        method_names = {
            item.name for item in engine_cls.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "generate" not in method_names:
            errors.append("SignalEngine class must define a 'generate' method")
        if "__init__" not in method_names:
            warnings.append("SignalEngine has no __init__ — parameters cannot be customized")

    # 5. Metadata extraction
    metadata = extract_strategy_metadata(source)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )


def validate_factor_source(source: str) -> ValidationResult:
    """Validate a factor source string.

    A factor is a module that defines a ``compute(panel)`` function (or a
    ``Factor`` class with a ``compute`` method).  The same security checks
    apply, but ``SignalEngine`` is not required.

    Returns a :class:`ValidationResult`.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Syntax
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ValidationResult(
            valid=False,
            errors=[f"Syntax error: {exc}"],
        )

    # 2. Structural (import-time)
    errors.extend(_validate_structure(tree))

    # 3. Runtime-reachable scrub (for Factor class, if present)
    factor_cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Factor"),
        None,
    )

    if factor_cls is not None:
        # Scan Factor class methods + transitive callees
        module_funcs = {
            n.name: n
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        worklist: list[ast.AST] = [
            m for m in factor_cls.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        visited: set[int] = set()
        while worklist:
            fn = worklist.pop()
            if id(fn) in visited:
                continue
            visited.add(id(fn))
            for node in ast.walk(fn):
                msg = _check_forbidden_node(node)
                if msg:
                    errors.append(msg)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    target = module_funcs.get(node.func.id)
                    if target is not None:
                        worklist.append(target)

        method_names = {
            item.name for item in factor_cls.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "compute" not in method_names:
            errors.append("Factor class must define a 'compute' method")
    else:
        # Check for module-level compute function
        has_compute = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "compute"
            for n in tree.body
        )
        if not has_compute:
            warnings.append(
                "No 'Factor' class or 'compute' function found — "
                "factor may not be usable in backtest"
            )

    # Also scan module-level functions for forbidden ops
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(n):
                msg = _check_forbidden_node(node)
                if msg:
                    errors.append(msg)

    # Metadata
    metadata: dict[str, Any] = {}
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        metadata["description"] = tree.body[0].value.value.strip().split("\n")[0][:200]

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        metadata=metadata,
    )
