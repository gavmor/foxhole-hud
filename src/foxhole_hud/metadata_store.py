import sqlite3
import os
import time
import json
from typing import Optional, Dict, Any, List

DEFAULT_DB_PATH = "/home/user/Documents/foxhole-hud/metadata/foxhole_metadata.db"

class MetadataStore:
    """
    Persistent SQLite metadata store for high-frequency CV telemetry,
    MCP consultation history, and BDI goal revisions.
    """
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.init_schema()

    def init_schema(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS frame_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    capture_latency_ms REAL,
                    cv_latency_ms REAL,
                    mode TEXT,
                    stamina_pct INTEGER,
                    stance TEXT,
                    has_shield INTEGER,
                    has_minimap INTEGER,
                    is_bleeding INTEGER,
                    is_map INTEGER,
                    player_x REAL,
                    player_y REAL
                )
            """)
            cur = self.conn.cursor()
            cur.execute("PRAGMA table_info(frame_metadata)")
            existing_cols = {row[1] for row in cur.fetchall()}
            desired_cols = {
                "mode": "TEXT",
                "stamina_pct": "INTEGER",
                "stance": "TEXT",
                "has_shield": "INTEGER",
                "has_minimap": "INTEGER",
                "is_bleeding": "INTEGER",
                "is_map": "INTEGER",
                "player_x": "REAL",
                "player_y": "REAL"
            }
            for col_name, col_type in desired_cols.items():
                if col_name not in existing_cols:
                    self.conn.execute(f"ALTER TABLE frame_metadata ADD COLUMN {col_name} {col_type}")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS mode_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    from_mode TEXT,
                    to_mode TEXT,
                    duration_s REAL
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_consultations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    tool_name TEXT,
                    query_params TEXT,
                    result_summary TEXT,
                    duration_ms REAL
                )
            """)

    def record_frame(self, capture_ms: float, cv_ms: float, state: Dict[str, Any], player_pos: Optional[tuple] = None):
        px, py = player_pos if player_pos else (None, None)
        with self.conn:
            self.conn.execute("""
                INSERT INTO frame_metadata 
                (timestamp, capture_latency_ms, cv_latency_ms, mode, stamina_pct, stance, has_shield, has_minimap, is_bleeding, is_map, player_x, player_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                capture_ms,
                cv_ms,
                state.get("mode", "PEDESTRIAN"),
                state.get("stamina_pct", 100),
                state.get("stance", "STAND"),
                1 if state.get("has_shield") else 0,
                1 if state.get("has_minimap") else 0,
                1 if state.get("is_bleeding") else 0,
                1 if state.get("is_map") else 0,
                px,
                py
            ))

    def record_transition(self, from_mode: str, to_mode: str, duration_s: float):
        with self.conn:
            self.conn.execute("""
                INSERT INTO mode_transitions (timestamp, from_mode, to_mode, duration_s)
                VALUES (?, ?, ?, ?)
            """, (time.time(), from_mode, to_mode, duration_s))

    def record_goal_revision(self, trigger: str, goal: str, strategic: str, tactical: str):
        """Deprecated compatibility stub: goal revisions replaced by mode transitions."""
        pass

    def record_mcp(self, tool_name: str, params: Dict[str, Any], summary: str, duration_ms: float):
        with self.conn:
            self.conn.execute("""
                INSERT INTO mcp_consultations (timestamp, tool_name, query_params, result_summary, duration_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (time.time(), tool_name, json.dumps(params), summary, duration_ms))

    def get_recent_metrics(self) -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*), AVG(capture_latency_ms), AVG(cv_latency_ms) FROM frame_metadata")
        row = cur.fetchone()
        count = row[0] or 0
        avg_cap = row[1] or 0.0
        avg_cv = row[2] or 0.0
        
        cur.execute("SELECT COUNT(*) FROM mcp_consultations")
        mcp_count = cur.fetchone()[0] or 0
        
        cur.execute("SELECT COUNT(*) FROM mode_transitions")
        trans_count = cur.fetchone()[0] or 0
        
        return {
            "total_frames_recorded": count,
            "avg_capture_ms": round(avg_cap, 2),
            "avg_cv_ms": round(avg_cv, 2),
            "total_mcp_consultations": mcp_count,
            "total_mode_transitions": trans_count
        }

    def close(self):
        self.conn.close()
