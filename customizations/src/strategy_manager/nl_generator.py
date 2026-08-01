"""Natural language to strategy code generator.

Uses the LLM provider to generate SignalEngine-compatible Python code
from a natural language description of a trading strategy.

The generated code is validated with the same AST validator used for
all user-submitted strategies, ensuring security and structural compliance.
"""

from __future__ import annotations

import logging
import re
import textwrap
from typing import Any

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Prompt template
# --------------------------------------------------------------------------- #
_SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert quantitative trading strategy developer.
    Your task is to generate a Python strategy class that follows the SignalEngine interface.

    Requirements:
    1. The code MUST define a class named `SignalEngine`.
    2. The class MUST have a `generate(self, data_map)` method.
    3. `data_map` is a Dict[str, pd.DataFrame] where keys are stock codes
       and each DataFrame has columns: open, high, low, close, volume.
    4. `generate` must return a Dict[str, pd.Series] of signal values
       (1.0 = buy, 0.0 = hold/neutral, -1.0 = sell).
    5. The `__init__` method should accept configurable parameters with defaults.
    6. Only use: pandas, numpy, and standard library. No other imports.
    7. Do NOT use: decorators, exec, eval, open, subprocess, os.system, or any I/O.
    8. Add a docstring at the top explaining the strategy.
    9. Keep the code clean, well-commented, and production-ready.

    Output ONLY the Python code, wrapped in ```python ... ``` markers.
    Do not add any explanation before or after the code block.
""")

_USER_PROMPT_TEMPLATE = "Generate a SignalEngine strategy for: {description}"


# --------------------------------------------------------------------------- #
# Code extraction
# --------------------------------------------------------------------------- #
_CODE_BLOCK_RE = re.compile(
    r"```(?:python)?\s*\n(.*?)```",
    re.DOTALL,
)


def _extract_code(raw: str) -> str:
    """Extract Python code from an LLM response.

    Handles:
    - ```python ... ``` fenced blocks
    - Bare code without fences
    """
    match = _CODE_BLOCK_RE.search(raw)
    if match:
        return match.group(1).strip()

    # If no code block found, try to use the raw text (stripped)
    # but only if it looks like Python code
    stripped = raw.strip()
    if "class SignalEngine" in stripped or "import " in stripped:
        return stripped

    return stripped


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_strategy_from_nl(
    description: str,
    *,
    llm: Any | None = None,
) -> tuple[str | None, str | None]:
    """Generate strategy code from a natural language description.

    Args:
        description: Natural language description of the desired strategy.
        llm: Optional pre-built LLM instance. If None, builds one.

    Returns:
        Tuple of (code, error). On success, error is None.
        On failure, code is None and error contains the message.
    """
    try:
        if llm is None:
            from src.providers.llm import build_llm
            llm = build_llm()

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=_USER_PROMPT_TEMPLATE.format(description=description)),
        ]

        logger.info("Generating strategy from NL: %s", description[:100])
        response = llm.invoke(messages)

        # Extract text from response
        raw_text = ""
        if isinstance(response, str):
            raw_text = response
        elif hasattr(response, "content"):
            raw_text = response.content if isinstance(response.content, str) else str(response.content)
        else:
            raw_text = str(response)

        code = _extract_code(raw_text)
        if not code:
            return None, "LLM response did not contain valid code"

        # Validate the generated code
        from src.strategy_manager.validator import validate_strategy_source

        result = validate_strategy_source(code)
        if not result.valid:
            error_msg = "Generated code failed validation:\n" + "\n".join(
                f"  - {e}" for e in result.errors
            )
            if result.warnings:
                error_msg += "\nWarnings:\n" + "\n".join(f"  - {w}" for w in result.warnings)
            logger.warning("NL-generated strategy failed validation: %s", result.errors)
            return None, error_msg

        logger.info("Successfully generated strategy from NL (%d chars)", len(code))
        return code, None

    except ImportError as e:
        logger.exception("Import error in NL generation: %s", e)
        return None, f"Required module not available: {e}"
    except Exception as e:  # noqa: BLE001
        logger.exception("NL generation failed: %s", e)
        return None, f"Generation failed: {e}"


def generate_factor_from_nl(
    description: str,
    *,
    llm: Any | None = None,
) -> tuple[str | None, str | None]:
    """Generate factor code from a natural language description.

    Similar to generate_strategy_from_nl but generates a Factor class
    with a `compute` method instead of SignalEngine.
    """
    factor_system_prompt = textwrap.dedent("""\
        You are an expert quantitative factor developer.
        Your task is to generate a Python factor class that follows the Factor interface.

        Requirements:
        1. The code MUST define a class named `Factor`.
        2. The class MUST have a `compute(self, panel)` method.
        3. `panel` is a pd.DataFrame with columns: open, high, low, close, volume.
        4. `compute` must return a pd.Series of factor values.
        5. The `__init__` method should accept configurable parameters with defaults.
        6. Only use: pandas, numpy, and standard library. No other imports.
        7. Do NOT use: decorators, exec, eval, open, subprocess, os.system, or any I/O.
        8. Add a docstring at the top explaining the factor.
        9. Keep the code clean, well-commented, and production-ready.

        Output ONLY the Python code, wrapped in ```python ... ``` markers.
    """)

    try:
        if llm is None:
            from src.providers.llm import build_llm
            llm = build_llm()

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=factor_system_prompt),
            HumanMessage(content=f"Generate a Factor for: {description}"),
        ]

        logger.info("Generating factor from NL: %s", description[:100])
        response = llm.invoke(messages)

        raw_text = ""
        if isinstance(response, str):
            raw_text = response
        elif hasattr(response, "content"):
            raw_text = response.content if isinstance(response.content, str) else str(response.content)
        else:
            raw_text = str(response)

        code = _extract_code(raw_text)
        if not code:
            return None, "LLM response did not contain valid code"

        # Validate
        from src.strategy_manager.validator import validate_factor_source

        result = validate_factor_source(code)
        if not result.valid:
            error_msg = "Generated factor failed validation:\n" + "\n".join(
                f"  - {e}" for e in result.errors
            )
            logger.warning("NL-generated factor failed validation: %s", result.errors)
            return None, error_msg

        logger.info("Successfully generated factor from NL (%d chars)", len(code))
        return code, None

    except Exception as e:  # noqa: BLE001
        logger.exception("Factor NL generation failed: %s", e)
        return None, f"Generation failed: {e}"
