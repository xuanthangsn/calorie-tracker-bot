"""JSON file storage with file lock and backup."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import Lock
from typing import Any

from filelock import FileLock

import config
from utils.helpers import now_local_iso, today_local


def _default_data() -> dict[str, Any]:
    return {
        "goals": {
            "daily": 2000,
            "weekly": 14000,
            "monthly": 60000,
            "updated_at": now_local_iso(),
        },
        "logs": [],
        "food_cache": {},
    }


class JsonStorage:
    _instance: JsonStorage | None = None
    _init_lock = Lock()

    def __init__(self) -> None:
        self._path = Path(config.DATA_FILE)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get(cls) -> JsonStorage:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            data = _default_data()
            self.save(data)
            return data
        with FileLock(str(self._lock_path), timeout=30):
            with self._path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def save(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self._lock_path), timeout=30):
            if self._path.exists():
                bak = self._path.with_suffix(self._path.suffix + ".bak")
                shutil.copy2(self._path, bak)
            tmp = self._path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(self._path)

    def _next_id(self, data: dict[str, Any]) -> int:
        logs = data.get("logs") or []
        if not logs:
            return 1
        return max(int(e["id"]) for e in logs) + 1

    def add_log(self, entry: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        entry = {**entry, "id": self._next_id(data)}
        if "date" not in entry:
            entry["date"] = today_local().isoformat()
        data.setdefault("logs", []).append(entry)
        self.save(data)
        return entry

    def update_log(self, log_id: int, new_data: dict[str, Any]) -> dict[str, Any] | None:
        data = self.load()
        logs = data.setdefault("logs", [])
        for i, e in enumerate(logs):
            if int(e["id"]) == int(log_id):
                merged = {**e, **new_data}
                logs[i] = merged
                self.save(data)
                return merged
        return None

    def delete_log(self, log_id: int) -> bool:
        data = self.load()
        logs = data.setdefault("logs", [])
        new_logs = [e for e in logs if int(e["id"]) != int(log_id)]
        if len(new_logs) == len(logs):
            return False
        data["logs"] = new_logs
        self.save(data)
        return True

    def get_logs_by_date(self, d: str) -> list[dict[str, Any]]:
        data = self.load()
        return [e for e in data.get("logs", []) if e.get("date") == d]

    def get_recent_logs(self, days: int = 2) -> list[dict[str, Any]]:
        from utils.helpers import date_range_last_n_days

        end = today_local()
        valid_dates = {d.isoformat() for d in date_range_last_n_days(days, end)}
        data = self.load()
        return [e for e in data.get("logs", []) if e.get("date") in valid_dates]

    def update_goals(self, updates: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        g = data.setdefault("goals", _default_data()["goals"])
        for k, v in updates.items():
            if k in ("daily", "weekly", "monthly") and v is not None:
                g[k] = int(v)
        g["updated_at"] = now_local_iso()
        self.save(data)
        return g

    def get_goals(self) -> dict[str, Any]:
        return dict(self.load().get("goals", _default_data()["goals"]))

    def get_food_cache(self) -> dict[str, Any]:
        return dict(self.load().get("food_cache", {}))

    def set_food_cache_entry(self, key: str, value: dict[str, Any]) -> None:
        data = self.load()
        data.setdefault("food_cache", {})[key] = value
        self.save(data)
