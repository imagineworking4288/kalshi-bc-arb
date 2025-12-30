import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from ..config import get_settings


class Database:
    def __init__(self):
        self.settings = get_settings()
        self.db_path = self.settings.database_path

    async def initialize(self):
        """Create database and tables"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(schema)
            await conn.commit()

        print(f"Database initialized: {self.db_path}")

    @asynccontextmanager
    async def connection(self):
        """Get async database connection"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn


db = Database()
