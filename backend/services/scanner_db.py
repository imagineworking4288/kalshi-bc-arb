"""
Scanner Database - Shared SQLite for scanner results.
Scanners write, API reads.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import threading

logger = logging.getLogger(__name__)

class ScannerDatabase:
    """Thread-safe database for scanner results."""

    def __init__(self, db_path: str = "./data/scanner_results.db"):
        self.db_path = db_path
        self._local = threading.local()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS scanner_results (
                scanner_type TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scanner_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanner_type TEXT NOT NULL,
                scan_count INTEGER,
                opportunities_found INTEGER,
                near_misses_found INTEGER,
                best_cost INTEGER,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_stats_type_time
            ON scanner_stats(scanner_type, timestamp);
        """)
        conn.commit()

    def save_scanner_result(self, scanner_type: str, result: Dict):
        """Save scanner result (called by scanner service)."""
        conn = self._get_conn()
        now = datetime.now().isoformat()

        conn.execute("""
            INSERT OR REPLACE INTO scanner_results (scanner_type, result_json, updated_at)
            VALUES (?, ?, ?)
        """, (scanner_type, json.dumps(result, default=str), now))

        stats = result.get("stats", {})
        conn.execute("""
            INSERT INTO scanner_stats
            (scanner_type, scan_count, opportunities_found, near_misses_found, best_cost, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            scanner_type,
            result.get("scan_count", 0),
            stats.get("total_arbitrage", len(result.get("opportunities", []))),
            stats.get("total_near_miss", len(result.get("near_misses", []))),
            stats.get("best_cost"),
            now
        ))

        conn.commit()

    def get_scanner_result(self, scanner_type: str) -> Optional[Dict]:
        """Get latest scanner result (called by API)."""
        conn = self._get_conn()
        row = conn.execute("""
            SELECT result_json, updated_at FROM scanner_results WHERE scanner_type = ?
        """, (scanner_type,)).fetchone()

        if row:
            result = json.loads(row["result_json"])
            result["_db_updated_at"] = row["updated_at"]
            return result
        return None

    def get_all_results(self) -> Dict[str, Dict]:
        """Get all scanner results."""
        conn = self._get_conn()
        rows = conn.execute("SELECT scanner_type, result_json, updated_at FROM scanner_results").fetchall()

        results = {}
        for row in rows:
            result = json.loads(row["result_json"])
            result["_db_updated_at"] = row["updated_at"]
            results[row["scanner_type"]] = result
        return results

    def get_scanner_history(self, scanner_type: str, limit: int = 100) -> list:
        """Get historical stats for a scanner."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM scanner_stats WHERE scanner_type = ? ORDER BY timestamp DESC LIMIT ?
        """, (scanner_type, limit)).fetchall()
        return [dict(row) for row in rows]
