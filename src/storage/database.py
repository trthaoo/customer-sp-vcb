import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.models import EventRecord, HandoverStateType
from src.config import DB_PATH

def init_db(db_path: str = DB_PATH):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
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
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_env_src ON events (env, source);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_channel ON events (channel, platform);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_handover ON events (flag, handover_state);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);")
        conn.commit()

class EventStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_db(self.db_path)

    def insert_event(self, event: EventRecord):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO events (
                    id, ts, env, source, channel, platform, surface,
                    intent, product_id, matched_rule, knowledge_files,
                    decision, flag, handover_state, reply_sent,
                    user_message, reply_text, escalate_reason, thread_id, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.id,
                event.ts,
                event.env,
                event.source,
                event.channel,
                event.platform,
                event.surface,
                event.intent,
                event.product_id,
                event.matched_rule,
                json.dumps(event.knowledge_files, ensure_ascii=False),
                event.decision,
                event.flag,
                event.handover_state,
                1 if event.reply_sent else 0,
                event.user_message,
                event.reply_text,
                event.escalate_reason,
                event.thread_id,
                event.user_id,
            ))
            conn.commit()

    def get_metrics(self, channel: str, platform_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates funnel metrics strictly for:
        env='prod' AND source='live' AND id NOT LIKE 'test_%' AND id NOT LIKE 'dry_%'
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
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
            cursor.execute(f"SELECT COUNT(*) as count FROM events {query}", params)
            inbound_count = cursor.fetchone()["count"]

            # Auto replied count
            cursor.execute(f"SELECT COUNT(*) as count FROM events {query} AND reply_sent = 1 AND flag = 'auto_reply'", params)
            auto_replied_count = cursor.fetchone()["count"]

            # Handover open count (open + claimed only)
            cursor.execute(f"SELECT COUNT(*) as count FROM events {query} AND flag = 'handover' AND handover_state IN ('open', 'claimed')", params)
            handover_open_count = cursor.fetchone()["count"]

            # Resolved count
            cursor.execute(f"SELECT COUNT(*) as count FROM events {query} AND handover_state = 'resolved'", params)
            resolved_count = cursor.fetchone()["count"]

            # Fallback count
            cursor.execute(f"SELECT COUNT(*) as count FROM events {query} AND decision = 'fallback'", params)
            fallback_count = cursor.fetchone()["count"]

            # Last event at
            cursor.execute(f"SELECT MAX(ts) as last_ts FROM events {query}", params)
            last_ts = cursor.fetchone()["last_ts"]

            # Top matched rules
            cursor.execute(f"""
                SELECT matched_rule, COUNT(*) as count 
                FROM events {query} AND matched_rule IS NOT NULL AND matched_rule != ''
                GROUP BY matched_rule 
                ORDER BY count DESC 
                LIMIT 5
            """, params)
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
        """
        Cross-channel handover queue.
        Strictly env='prod' AND source='live' AND id NOT LIKE 'test_%' AND id NOT LIKE 'dry_%' AND flag='handover'
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
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
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                item["reply_sent"] = bool(item["reply_sent"])
                try:
                    item["knowledge_files"] = json.loads(item["knowledge_files"]) if item["knowledge_files"] else []
                except Exception:
                    item["knowledge_files"] = []
                result.append(item)
            return result

    def get_handover_badge_count(self) -> int:
        """
        Returns count of open + claimed handover cases.
        Strictly env='prod' AND source='live'.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM events 
                WHERE env = 'prod' 
                  AND source = 'live' 
                  AND id NOT LIKE 'test_%' 
                  AND id NOT LIKE 'dry_%'
                  AND flag = 'handover' 
                  AND handover_state IN ('open', 'claimed')
            """)
            row = cursor.fetchone()
            return row[0] if row else 0

    def resolve_handover(self, event_id: str, operator_notes: str = "") -> bool:
        """
        Updates an existing handover case to resolved, and writes a real audit event.
        Do not auto-resolve!
        """
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE events 
                SET handover_state = 'resolved' 
                WHERE id = ? AND env = 'prod' AND source = 'live'
            """, (event_id,))
            
            if cursor.rowcount > 0:
                # Log a real resolution event
                audit_id = f"res_{event_id}_{int(datetime.now(timezone.utc).timestamp())}"
                cursor.execute("""
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
                """, (audit_id, now, operator_notes, event_id))
                conn.commit()
                return True
            conn.commit()
            return False

    def update_handover_state(self, event_id: str, new_state: HandoverStateType) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE events 
                SET handover_state = ? 
                WHERE id = ? AND env = 'prod' AND source = 'live'
            """, (new_state, event_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_recent_events(self, channel: Optional[str] = None, platform: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
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
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["reply_sent"] = bool(item["reply_sent"])
                try:
                    item["knowledge_files"] = json.loads(item["knowledge_files"]) if item["knowledge_files"] else []
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
