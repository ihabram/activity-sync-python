import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.getenv("SQLITE_DB_PATH", "activities.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initialize the SQLite schema."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                strava_id INTEGER PRIMARY KEY,
                garmin_id INTEGER NOT NULL,
                activity_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_garmin_id(strava_id: int) -> Optional[int]:
    """Retrieve the mapped Garmin activity ID for a given Strava activity ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT garmin_id FROM activities WHERE strava_id = ?", (strava_id,))
        row = cursor.fetchone()
        return row["garmin_id"] if row else None

def save_mapping(strava_id: int, garmin_id: int, activity_name: str = "") -> None:
    """Save or update the mapping between Strava activity ID and Garmin activity ID."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO activities (strava_id, garmin_id, activity_name, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(strava_id) DO UPDATE SET
                garmin_id = excluded.garmin_id,
                activity_name = excluded.activity_name,
                updated_at = excluded.updated_at
        """, (strava_id, garmin_id, activity_name, datetime.utcnow()))
        conn.commit()

def get_recent_synced(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recently synced activities for status inspection."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strava_id, garmin_id, activity_name, updated_at 
            FROM activities 
            ORDER BY updated_at DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
