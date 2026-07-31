import re
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine, Result


_INSERT_ID_TABLES = {
    "users",
    "activity_logs",
    "job_applications",
    "resume_sources",
    "match_analyses",
    "match_items",
    "resumes",
    "resume_versions",
    "resume_suggestions",
    "resume_suggestion_events",
    "resume_exports",
    "invite_codes",
}
_INSERT_TABLE_RE = re.compile(r"^\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)


class DatabaseConfigurationError(RuntimeError):
    pass


class CompatRow(Mapping[str, Any]):
    """Small sqlite3.Row-compatible view over a SQLAlchemy row mapping."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)
        self._keys = tuple(self._values)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[self._keys[key]]
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class CompatResult:
    def __init__(self, result: Result[Any], lastrowid: int | None = None) -> None:
        self._result = result
        self.lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return self._result.rowcount

    def fetchone(self) -> CompatRow | None:
        row = self._result.fetchone()
        return CompatRow(row._mapping) if row is not None else None

    def fetchall(self) -> list[CompatRow]:
        return [CompatRow(row._mapping) for row in self._result.fetchall()]

    def __iter__(self) -> Iterator[CompatRow]:
        for row in self._result:
            yield CompatRow(row._mapping)


class CompatConnection:
    def __init__(self, connection: Connection, dialect_name: str) -> None:
        self._connection = connection
        self._dialect_name = dialect_name

    def execute(
        self, statement: str, parameters: Sequence[Any] | None = None
    ) -> CompatResult:
        if statement.strip().upper() == "BEGIN IMMEDIATE":
            if self._dialect_name == "sqlite":
                return CompatResult(self._connection.exec_driver_sql("BEGIN IMMEDIATE"))
            return CompatResult(self._connection.execute(text("SELECT 1 WHERE 0 = 1")))

        sql, bindings = self._bind(statement, parameters or ())
        insert_match = _INSERT_TABLE_RE.match(sql)
        returns_id = (
            self._dialect_name == "postgresql"
            and insert_match is not None
            and insert_match.group(1).lower() in _INSERT_ID_TABLES
            and " returning " not in f" {sql.lower()} "
        )
        if returns_id:
            sql = f"{sql.rstrip().rstrip(';')} RETURNING id"
        result = self._connection.execute(text(sql), bindings)
        if returns_id:
            inserted_id = result.scalar_one()
            return CompatResult(result, int(inserted_id))
        raw_lastrowid = getattr(result, "lastrowid", None)
        lastrowid = int(raw_lastrowid) if raw_lastrowid is not None else None
        return CompatResult(result, lastrowid)

    @staticmethod
    def _bind(
        statement: str, parameters: Sequence[Any]
    ) -> tuple[str, dict[str, Any]]:
        pieces = statement.split("?")
        placeholder_count = len(pieces) - 1
        if placeholder_count != len(parameters):
            if placeholder_count == 0 and not parameters:
                return statement, {}
            raise ValueError(
                f"SQL placeholder count {placeholder_count} does not match "
                f"parameter count {len(parameters)}"
            )
        if not placeholder_count:
            return statement, {}
        output = pieces[0]
        bindings: dict[str, Any] = {}
        for index, value in enumerate(parameters):
            name = f"p{index}"
            bindings[name] = value
            output += f":{name}{pieces[index + 1]}"
        return output, bindings


class _ConnectionScope(AbstractContextManager[CompatConnection]):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._transaction: AbstractContextManager[Connection] | None = None

    def __enter__(self) -> CompatConnection:
        self._transaction = self._engine.begin()
        connection = self._transaction.__enter__()
        return CompatConnection(connection, self._engine.dialect.name)

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool | None:
        if self._transaction is None:
            return None
        return self._transaction.__exit__(exc_type, exc_value, traceback)


class Database:
    def __init__(self, database_url: str, schema_path: Path) -> None:
        self.database_url = database_url
        self.schema_path = schema_path
        connect_args: dict[str, Any] = {}
        if database_url.startswith("sqlite:"):
            connect_args["check_same_thread"] = False
        self.engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name

    def connect(self) -> _ConnectionScope:
        return _ConnectionScope(self.engine)

    def initialize(self) -> None:
        if self.dialect_name == "sqlite":
            path = self.sqlite_path
            if path is None:
                raise DatabaseConfigurationError("SQLite database path is unavailable")
            path.parent.mkdir(parents=True, exist_ok=True)
            schema = self.schema_path.read_text(encoding="utf-8")
            with sqlite3.connect(path) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executescript(schema)
            return

        # Production schema changes are deliberately managed by Alembic.
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM users LIMIT 1"))

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @property
    def sqlite_path(self) -> Path | None:
        if self.dialect_name != "sqlite":
            return None
        database = self.engine.url.database
        if not database or database == ":memory:":
            return None
        return Path(database).resolve()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()
