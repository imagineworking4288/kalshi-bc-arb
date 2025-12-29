"""Database connection and initialization"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from ..config import get_settings


class Database:
    """SQLite database manager"""

    def __init__(self):
        settings = get_settings()
        self.db_path = settings.database_path
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database with schema"""
        if self._initialized:
            return

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Read and execute schema
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(schema)
            await db.commit()

        self._initialized = True

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get database connection as async context manager"""
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def execute(self, query: str, params: tuple = ()) -> None:
        """Execute a single query"""
        async with self.get_connection() as db:
            await db.execute(query, params)
            await db.commit()

    async def execute_many(self, query: str, params_list: list) -> None:
        """Execute a query with multiple parameter sets"""
        async with self.get_connection() as db:
            await db.executemany(query, params_list)
            await db.commit()

    async def fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        """Fetch a single row"""
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows"""
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Global database instance
db = Database()
