import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.models import EventRecord, HandoverStateType
from src.config import DB_PATH, DATABASE_URL

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class EventStore:
    def __init__(self, db_path: str = DB_PATH, database_url: Optional[str] = None):
        self.db_path = db_path
        # Use DATABASE_URL if explicitly given or if configured in env
        # Note: If db_path was explicitly passed as a test temp path (e.g. contains test/tmp), prefer sqlite
        env_db_url = database_url or DATABASE_URL
        if env_db_url and POSTGRES_AVAILABLE and ("postgres://" in env_db_url or "postgresql://" in env_db_url) and not ("test" in db_path.lower() or "tmp" in db_path.lower()):
            self.database_url = env_db_url
            self.is_postgres = True
        else:
            self.database_url = None
            self.is_postgres = False

        self._init_db()

    def _get_connection(self):
        if self.is_postgres:
            return psycopg2.connect(self.database_url)
        p = Path(self.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _format_sql(self, sql: str) -> str:
        if self.is_postgres:
            return sql.replace("?", "%s")
        return sql

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    env TEXT NOT NULL,
                    source TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    product_id TEXT,
                    matched_rule TEXT,
                    knowledge_files TEXT,
                    decision TEXT NOT NULL,
                    flag TEXT NOT NULL,
                    handover_state TEXT,
                    reply_sent INTEGER NOT NULL DEFAULT 0,
                    user_message TEXT,
                    reply_text TEXT,
                    escalate_reason TEXT,
                    thread_id TEXT,
                    user_id TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_env_src ON events (env, source);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_channel ON events (channel, platform);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_handover ON events (flag, handover_state);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);")

            # 2. Chat Sessions Table (Persistent session-level conversation logs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    thread_id TEXT,
                    user_id TEXT,
                    user_name TEXT,
                    turn_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_message TEXT,
                    last_reply TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    turns_data TEXT NOT NULL DEFAULT '[]'
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions (updated_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_chan ON chat_sessions (channel, platform);")
            conn.commit()

    def insert_event(self, event: EventRecord):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            kf_json = json.dumps(event.knowledge_files, ensure_ascii=False)
            reply_sent_int = 1 if event.reply_sent else 0

            if self.is_postgres:
                sql = """
                    INSERT INTO events (
                        id, ts, env, source, channel, platform, surface,
                        intent, product_id, matched_rule, knowledge_files,
                        decision, flag, handover_state, reply_sent,
                        user_message, reply_text, escalate_reason, thread_id, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        ts = EXCLUDED.ts,
                        env = EXCLUDED.env,
                        source = EXCLUDED.source,
                        channel = EXCLUDED.channel,
                        platform = EXCLUDED.platform,
                        surface = EXCLUDED.surface,
                        intent = EXCLUDED.intent,
                        product_id = EXCLUDED.product_id,
                        matched_rule = EXCLUDED.matched_rule,
                        knowledge_files = EXCLUDED.knowledge_files,
                        decision = EXCLUDED.decision,
                        flag = EXCLUDED.flag,
                        handover_state = EXCLUDED.handover_state,
                        reply_sent = EXCLUDED.reply_sent,
                        user_message = EXCLUDED.user_message,
                        reply_text = EXCLUDED.reply_text,
                        escalate_reason = EXCLUDED.escalate_reason,
                        thread_id = EXCLUDED.thread_id,
                        user_id = EXCLUDED.user_id;
                """
                cursor.execute(sql, (
                    event.id, event.ts, event.env, event.source, event.channel, event.platform, event.surface,
                    event.intent, event.product_id, event.matched_rule, kf_json,
                    event.decision, event.flag, event.handover_state, reply_sent_int,
                    event.user_message, event.reply_text, event.escalate_reason, event.thread_id, event.user_id
                ))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO events (
                        id, ts, env, source, channel, platform, surface,
                        intent, product_id, matched_rule, knowledge_files,
                        decision, flag, handover_state, reply_sent,
                        user_message, reply_text, escalate_reason, thread_id, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.id, event.ts, event.env, event.source, event.channel, event.platform, event.surface,
                    event.intent, event.product_id, event.matched_rule, kf_json,
                    event.decision, event.flag, event.handover_state, reply_sent_int,
                    event.user_message, event.reply_text, event.escalate_reason, event.thread_id, event.user_id
                ))
            conn.commit()

    # --- CHAT SESSION LOGS METHODS ---
    def save_session_turn(
        self,
        session_id: str,
        channel: str,
        platform: str,
        surface: str,
        user_message: str,
        reply: str,
        turn_data: Dict[str, Any],
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        status: str = "active"
    ):
        """
        Saves or appends a turn to a chat session log.
        Creates the session if it doesn't exist, or appends the turn and updates counters.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            # Check if session exists
            select_sql = self._format_sql("SELECT id, turns_data, turn_count, created_at FROM chat_sessions WHERE id = ?")
            cursor.execute(select_sql, (session_id,))
            row = cursor.fetchone()

            if row:
                row_dict = dict(row)
                try:
                    turns = json.loads(row_dict["turns_data"]) if row_dict.get("turns_data") else []
                except Exception:
                    turns = []
                turns.append(turn_data)
                turns_json = json.dumps(turns, ensure_ascii=False)
                new_count = len(turns)

                update_sql = self._format_sql("""
                    UPDATE chat_sessions
                    SET turn_count = ?,
                        updated_at = ?,
                        last_message = ?,
                        last_reply = ?,
                        status = ?,
                        turns_data = ?
                    WHERE id = ?
                """)
                cursor.execute(update_sql, (new_count, now, user_message, reply, status, turns_json, session_id))
            else:
                turns = [turn_data]
                turns_json = json.dumps(turns, ensure_ascii=False)
                insert_sql = self._format_sql("""
                    INSERT INTO chat_sessions (
                        id, channel, platform, surface, thread_id, user_id, user_name,
                        turn_count, created_at, updated_at, last_message, last_reply, status, turns_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """)
                cursor.execute(insert_sql, (
                    session_id, channel, platform, surface, thread_id or session_id,
                    user_id or "user", user_name or "Khách Hàng", 1, now, now,
                    user_message, reply, status, turns_json
                ))
            conn.commit()

    def get_chat_sessions(
        self,
        channel: Optional[str] = None,
        platform: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            conditions = ["1=1"]
            params: List[Any] = []

            if channel and channel != "all":
                conditions.append("channel = ?")
                params.append(channel)
            if platform and platform != "all":
                conditions.append("platform = ?")
                params.append(platform)
            if search:
                conditions.append("(id LIKE ? OR last_message LIKE ? OR user_name LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])

            where_clause = " AND ".join(conditions)
            sql = f"""
                SELECT id, channel, platform, surface, thread_id, user_id, user_name,
                       turn_count, created_at, updated_at, last_message, last_reply, status
                FROM chat_sessions
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(self._format_sql(sql), params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            sql = self._format_sql("SELECT * FROM chat_sessions WHERE id = ?")
            cursor.execute(sql, (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["turns"] = json.loads(res["turns_data"]) if res.get("turns_data") else []
            except Exception:
                res["turns"] = []
            return res

    def delete_chat_session(self, session_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = self._format_sql("DELETE FROM chat_sessions WHERE id = ?")
            cursor.execute(sql, (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- METRICS & HANDOVER METHODS ---
    def get_metrics(self, channel: str, platform_filter: Optional[str] = None) -> Dict[str, Any]:
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            query = """
                WHERE env = 'prod' 
                  AND source = 'live' 
                  AND id NOT LIKE 'test_%' 
                  AND id NOT LIKE 'dry_%'
                  AND channel = ?
            """
            params: List[Any] = [channel]

            if platform_filter and platform_filter != "all":
                query += " AND platform = ?"
                params.append(platform_filter)

            # Inbound count
            cursor.execute(self._format_sql(f"SELECT COUNT(*) as count FROM events {query}"), params)
            inbound_count = cursor.fetchone()["count"]

            # Auto replied count
            cursor.execute(self._format_sql(f"SELECT COUNT(*) as count FROM events {query} AND reply_sent = 1 AND flag = 'auto_reply'"), params)
            auto_replied_count = cursor.fetchone()["count"]

            # Handover open count (open + claimed only)
            cursor.execute(self._format_sql(f"SELECT COUNT(*) as count FROM events {query} AND flag = 'handover' AND handover_state IN ('open', 'claimed')"), params)
            handover_open_count = cursor.fetchone()["count"]

            # Resolved count
            cursor.execute(self._format_sql(f"SELECT COUNT(*) as count FROM events {query} AND handover_state = 'resolved'"), params)
            resolved_count = cursor.fetchone()["count"]

            # Fallback count
            cursor.execute(self._format_sql(f"SELECT COUNT(*) as count FROM events {query} AND decision = 'fallback'"), params)
            fallback_count = cursor.fetchone()["count"]

            # Last event at
            cursor.execute(self._format_sql(f"SELECT MAX(ts) as last_ts FROM events {query}"), params)
            last_ts = cursor.fetchone()["last_ts"]

            # Top matched rules
            cursor.execute(self._format_sql(f"""
                SELECT matched_rule, COUNT(*) as count 
                FROM events {query} AND matched_rule IS NOT NULL AND matched_rule != ''
                GROUP BY matched_rule 
                ORDER BY count DESC 
                LIMIT 5
            """), params)
            top_rules = [{"rule": r["matched_rule"], "count": r["count"]} for r in cursor.fetchall()]

            return {
                "inbound_count": inbound_count,
                "auto_replied_count": auto_replied_count,
                "handover_open_count": handover_open_count,
                "resolved_count": resolved_count,
                "fallback_count": fallback_count,
                "last_event_at": last_ts,
                "top_matched_rules": top_rules
            }

    def get_handover_queue(self, channel: Optional[str] = None, state_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            query = """
                SELECT * FROM events 
                WHERE env = 'prod' 
                  AND source = 'live' 
                  AND id NOT LIKE 'test_%' 
                  AND id NOT LIKE 'dry_%'
                  AND flag = 'handover'
            """
            params: List[Any] = []

            if channel:
                query += " AND channel = ?"
                params.append(channel)

            if state_filter and state_filter != "all":
                query += " AND handover_state = ?"
                params.append(state_filter)

            query += " ORDER BY ts DESC"
            cursor.execute(self._format_sql(query), params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["reply_sent"] = bool(item["reply_sent"])
                try:
                    item["knowledge_files"] = json.loads(item["knowledge_files"]) if item.get("knowledge_files") else []
                except Exception:
                    item["knowledge_files"] = []
                result.append(item)
            return result

    def get_handover_badge_count(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self._format_sql("""
                SELECT COUNT(*) FROM events 
                WHERE env = 'prod' 
                  AND source = 'live' 
                  AND id NOT LIKE 'test_%' 
                  AND id NOT LIKE 'dry_%'
                  AND flag = 'handover' 
                  AND handover_state IN ('open', 'claimed')
            """))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return list(row.values())[0]
                return row[0]
            return 0

    def resolve_handover(self, event_id: str, operator_notes: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self._format_sql("""
                UPDATE events 
                SET handover_state = 'resolved' 
                WHERE id = ? AND env = 'prod' AND source = 'live'
            """), (event_id,))
            
            if cursor.rowcount > 0:
                audit_id = f"res_{event_id}_{int(datetime.now(timezone.utc).timestamp())}"
                cursor.execute(self._format_sql("""
                    INSERT INTO events (
                        id, ts, env, source, channel, platform, surface,
                        intent, product_id, matched_rule, knowledge_files,
                        decision, flag, handover_state, reply_sent,
                        user_message, reply_text, escalate_reason, thread_id, user_id
                    ) SELECT 
                        ?, ?, env, source, channel, platform, surface,
                        'handover_resolved', product_id, matched_rule, knowledge_files,
                        'escalate', 'handover', 'resolved', 0,
                        'OPERATOR RESOLVE: ' || ?, reply_text, escalate_reason, thread_id, user_id
                    FROM events WHERE id = ?
                """), (audit_id, now, operator_notes, event_id))
                conn.commit()
                return True
            conn.commit()
            return False

    def update_handover_state(self, event_id: str, new_state: HandoverStateType) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(self._format_sql("""
                UPDATE events 
                SET handover_state = ? 
                WHERE id = ? AND env = 'prod' AND source = 'live'
            """), (new_state, event_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_recent_events(self, channel: Optional[str] = None, platform: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if self.is_postgres:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()

            query = """
                SELECT * FROM events 
                WHERE env = 'prod' 
                  AND source = 'live' 
                  AND id NOT LIKE 'test_%' 
                  AND id NOT LIKE 'dry_%'
            """
            params: List[Any] = []
            if channel:
                query += " AND channel = ?"
                params.append(channel)
            if platform and platform != "all":
                query += " AND platform = ?"
                params.append(platform)
            query += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            cursor.execute(self._format_sql(query), params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["reply_sent"] = bool(item["reply_sent"])
                try:
                    item["knowledge_files"] = json.loads(item["knowledge_files"]) if item.get("knowledge_files") else []
                except Exception:
                    item["knowledge_files"] = []
                result.append(item)
            return result


_db_instance: Optional[EventStore] = None

def get_event_store(db_path: str = DB_PATH) -> EventStore:
    global _db_instance
    if _db_instance is None or _db_instance.db_path != db_path:
        _db_instance = EventStore(db_path)
    return _db_instance
