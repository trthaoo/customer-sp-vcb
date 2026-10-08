import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal

from src.config import BASE_DIR

DATA_DIR = Path(BASE_DIR) / "data"
GOLDEN_EXAMPLES_FILE = DATA_DIR / "golden_examples.json"
FAILED_CASES_FILE = DATA_DIR / "failed_cases.json"

class TestCaseManager:
    """
    Manages persistence and retrieval of test session ratings:
    - Golden Examples (Pass / Đạt): Reference benchmark cases for regression testing & few-shot examples.
    - Failed Cases (Fail / Không đạt): Detailed audit logs with root cause analysis & actionable fixes to prevent recurrence.
    """
    __test__ = False

    def __init__(self, golden_file: Path = GOLDEN_EXAMPLES_FILE, failed_file: Path = FAILED_CASES_FILE):
        self.golden_file = Path(golden_file)
        self.failed_file = Path(failed_file)
        self._ensure_storage()

    def _ensure_storage(self):
        self.golden_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.golden_file.exists():
            self.golden_file.write_text("[]", encoding="utf-8")
        if not self.failed_file.exists():
            self.failed_file.write_text("[]", encoding="utf-8")

    def _load_json(self, path: Path) -> List[Dict[str, Any]]:
        try:
            if not path.exists():
                return []
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            return json.loads(content)
        except Exception:
            return []

    def _save_json(self, path: Path, data: List[Dict[str, Any]]):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    # 1. Save Golden Example (Đạt)
    def save_golden_example(
        self,
        session_id: str,
        channel: str,
        platform: str,
        surface: str,
        turns: List[Dict[str, Any]],
        title: Optional[str] = None,
        notes: Optional[str] = "",
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        cases = self._load_json(self.golden_file)
        case_id = f"gold_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Generate default title if not provided
        if not title:
            first_msg = ""
            for t in turns:
                first_msg = t.get("customer_message") or t.get("customerMessage") or ""
                if first_msg:
                    break
            title = first_msg[:60] if first_msg else f"Example {session_id}"

        record = {
            "id": case_id,
            "session_id": session_id,
            "created_at": now_iso,
            "rating": "pass",
            "channel": channel,
            "platform": platform,
            "surface": surface,
            "title": title,
            "notes": notes or "",
            "tags": tags or [channel, platform, surface],
            "turn_count": len(turns),
            "turns": turns
        }

        cases.insert(0, record)  # Newest first
        self._save_json(self.golden_file, cases)
        return record

    # 2. Save Failed Case (Fail)
    def save_failed_case(
        self,
        session_id: str,
        channel: str,
        platform: str,
        surface: str,
        turns: List[Dict[str, Any]],
        error_category: str,
        root_cause: str,
        suggested_fix: str,
        target_file_to_fix: Optional[str] = "",
        failed_turn_index: Optional[int] = None,
        notes: Optional[str] = ""
    ) -> Dict[str, Any]:
        cases = self._load_json(self.failed_file)
        case_id = f"fail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        category_labels = {
            "sai_chinh_sach": "Sai chính sách (Returns / Shipping / Warranty / Payment)",
            "sai_san_pham": "Sai sản phẩm / Sai giá USD / Sai chất liệu",
            "khong_dat_tieu_chuan": "Không đạt tiêu chuẩn / Bịa thông tin / Sai Brand Voice",
            "sai_handover": "Xử lý sai Handover (Không chuyển người hoặc chuyển nhầm)",
            "khac": "Lỗi khác"
        }

        record = {
            "id": case_id,
            "session_id": session_id,
            "created_at": now_iso,
            "rating": "fail",
            "channel": channel,
            "platform": platform,
            "surface": surface,
            "error_category": error_category,
            "error_category_label": category_labels.get(error_category, error_category),
            "failed_turn_index": failed_turn_index,
            "root_cause": root_cause,
            "suggested_fix": suggested_fix,
            "target_file_to_fix": target_file_to_fix or "",
            "status": "open",  # "open" | "fixed"
            "fixed_at": None,
            "fixed_notes": "",
            "notes": notes or "",
            "turn_count": len(turns),
            "turns": turns
        }

        cases.insert(0, record)  # Newest first
        self._save_json(self.failed_file, cases)
        return record

    # 3. Retrieve all cases
    def get_all_cases(self) -> Dict[str, Any]:
        golden = self._load_json(self.golden_file)
        failed = self._load_json(self.failed_file)

        open_failed = sum(1 for c in failed if c.get("status") == "open")
        fixed_failed = sum(1 for c in failed if c.get("status") == "fixed")

        return {
            "golden_examples": golden,
            "failed_cases": failed,
            "stats": {
                "total_rated": len(golden) + len(failed),
                "golden_count": len(golden),
                "failed_count": len(failed),
                "open_failed_count": open_failed,
                "fixed_failed_count": fixed_failed
            }
        }

    # 4. Update status of failed case (e.g. mark as fixed)
    def update_failed_case_status(self, case_id: str, status: Literal["open", "fixed"], fixed_notes: Optional[str] = "") -> Optional[Dict[str, Any]]:
        cases = self._load_json(self.failed_file)
        updated = None
        for c in cases:
            if c["id"] == case_id:
                c["status"] = status
                if status == "fixed":
                    c["fixed_at"] = datetime.now(timezone.utc).isoformat()
                    if fixed_notes:
                        c["fixed_notes"] = fixed_notes
                else:
                    c["fixed_at"] = None
                updated = c
                break

        if updated:
            self._save_json(self.failed_file, cases)
        return updated

    # 5. Delete a case
    def delete_case(self, case_type: Literal["golden", "failed"], case_id: str) -> bool:
        target_file = self.golden_file if case_type == "golden" else self.failed_file
        cases = self._load_json(target_file)
        new_cases = [c for c in cases if c.get("id") != case_id]
        if len(new_cases) != len(cases):
            self._save_json(target_file, new_cases)
            return True
        return False

_manager: Optional[TestCaseManager] = None

def get_test_case_manager() -> TestCaseManager:
    global _manager
    if _manager is None:
        _manager = TestCaseManager()
    return _manager
