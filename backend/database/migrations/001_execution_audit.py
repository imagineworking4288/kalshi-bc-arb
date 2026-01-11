"""
Migration 001: Add execution audit system tables

This migration:
1. Creates the execution_audit table if it doesn't exist
2. Drops and recreates circuit_breaker_state with new schema
3. Adds audit_id column to btc_arb_executions table

Run with: python -m backend.database.migrations.001_execution_audit
"""

import asyncio
import logging
from pathlib import Path

import aiosqlite

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "kalshi.db"


async def table_exists(conn: aiosqlite.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    result = await cursor.fetchone()
    return result is not None


async def column_exists(conn: aiosqlite.Connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor = await conn.execute(f"PRAGMA table_info({table_name})")
    columns = await cursor.fetchall()
    return any(col[1] == column_name for col in columns)


async def migrate_execution_audit(conn: aiosqlite.Connection) -> bool:
    """Create execution_audit table if it doesn't exist."""
    if await table_exists(conn, "execution_audit"):
        logger.info("Table 'execution_audit' already exists, skipping creation")
        return False

    logger.info("Creating 'execution_audit' table...")
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS execution_audit (
            id TEXT PRIMARY KEY,
            request_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK (source IN ('orchestrator', 'manual', 'auto_trader', 'btc_arb', 'strategy')),
            signal_id TEXT,
            mode TEXT NOT NULL CHECK (mode IN ('paper', 'live', 'dual')),
            legs_json TEXT NOT NULL,
            atomic INTEGER NOT NULL DEFAULT 1,
            max_slippage_cents INTEGER,
            success INTEGER NOT NULL,
            total_cost_cents INTEGER,
            total_fees_cents INTEGER,
            execution_time_ms INTEGER,
            leg_results_json TEXT,
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_exec_audit_source ON execution_audit(source);
        CREATE INDEX IF NOT EXISTS idx_exec_audit_mode ON execution_audit(mode);
        CREATE INDEX IF NOT EXISTS idx_exec_audit_created ON execution_audit(created_at);
        CREATE INDEX IF NOT EXISTS idx_exec_audit_request ON execution_audit(request_id);
    """)
    logger.info("Created 'execution_audit' table with indexes")
    return True


async def migrate_circuit_breaker_state(conn: aiosqlite.Connection) -> bool:
    """Drop and recreate circuit_breaker_state with new schema."""
    needs_migration = False

    if await table_exists(conn, "circuit_breaker_state"):
        # Check if it has the new schema (look for 'tripped' column instead of 'is_tripped')
        if await column_exists(conn, "circuit_breaker_state", "is_tripped"):
            needs_migration = True
            logger.info("Old 'circuit_breaker_state' schema detected, will recreate")
        elif not await column_exists(conn, "circuit_breaker_state", "permanent"):
            needs_migration = True
            logger.info("'circuit_breaker_state' missing new columns, will recreate")
        else:
            logger.info("Table 'circuit_breaker_state' already has new schema, skipping")
            return False
    else:
        needs_migration = True
        logger.info("Table 'circuit_breaker_state' does not exist, will create")

    if needs_migration:
        logger.info("Dropping and recreating 'circuit_breaker_state' table...")
        await conn.executescript("""
            DROP TABLE IF EXISTS circuit_breaker_state;

            CREATE TABLE circuit_breaker_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                tripped INTEGER NOT NULL DEFAULT 0,
                trip_reason TEXT,
                trip_time TIMESTAMP,
                permanent INTEGER NOT NULL DEFAULT 0,
                consecutive_losses INTEGER NOT NULL DEFAULT 0,
                daily_loss_cents INTEGER NOT NULL DEFAULT 0,
                hourly_trades_json TEXT,
                hourly_exposure_json TEXT,
                last_reset_date TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO circuit_breaker_state (id) VALUES (1);
        """)
        logger.info("Created 'circuit_breaker_state' table with new schema")
        return True

    return False


async def migrate_btc_arb_executions(conn: aiosqlite.Connection) -> bool:
    """Add audit_id column to btc_arb_executions if missing."""
    if not await table_exists(conn, "btc_arb_executions"):
        logger.info("Table 'btc_arb_executions' does not exist, skipping column addition")
        return False

    if await column_exists(conn, "btc_arb_executions", "audit_id"):
        logger.info("Column 'audit_id' already exists in btc_arb_executions, skipping")
        return False

    logger.info("Adding 'audit_id' column to btc_arb_executions...")
    await conn.execute("ALTER TABLE btc_arb_executions ADD COLUMN audit_id TEXT")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_btc_arb_exec_audit ON btc_arb_executions(audit_id)")
    logger.info("Added 'audit_id' column and index to btc_arb_executions")
    return True


async def run_migration(db_path: Path | None = None) -> dict:
    """
    Run the migration.

    Args:
        db_path: Path to the database file. Defaults to data/kalshi.db

    Returns:
        Dict with migration results
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    logger.info(f"Running migration on database: {db_path}")

    if not db_path.exists():
        logger.warning(f"Database file does not exist: {db_path}")
        logger.info("Creating new database with migration tables...")
        db_path.parent.mkdir(parents=True, exist_ok=True)

    results = {
        "execution_audit": False,
        "circuit_breaker_state": False,
        "btc_arb_executions": False,
    }

    async with aiosqlite.connect(db_path) as conn:
        results["execution_audit"] = await migrate_execution_audit(conn)
        results["circuit_breaker_state"] = await migrate_circuit_breaker_state(conn)
        results["btc_arb_executions"] = await migrate_btc_arb_executions(conn)
        await conn.commit()

    logger.info(f"Migration complete: {results}")
    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run execution audit migration")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to database file (default: data/kalshi.db)"
    )
    args = parser.parse_args()

    results = asyncio.run(run_migration(args.db_path))

    if any(results.values()):
        print("Migration applied changes:")
        for table, changed in results.items():
            status = "CREATED/UPDATED" if changed else "NO CHANGE"
            print(f"  - {table}: {status}")
    else:
        print("No changes needed, database already up to date")


if __name__ == "__main__":
    main()
