"""Strategy & Factor persistent storage module.

Provides database-backed CRUD, version management, and AST validation
for user-defined strategies and factors.

Database: ~/.vibe-trading/strategies.db (SQLite, WAL mode)
"""
