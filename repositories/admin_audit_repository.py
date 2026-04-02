import json
from pathlib import Path
from typing import Any


class AdminAuditRepository:
    def __init__(self, path: Path, max_entries: int = 100) -> None:
        self.path = path
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text('[]', encoding='utf-8')

    def _read(self) -> list[dict[str, Any]]:
        try:
            raw = self.path.read_text(encoding='utf-8').strip()
            if not raw:
                return []
            data = json.loads(raw)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def _write(self, entries: list[dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(entries[-self.max_entries:], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    def append(self, entry: dict[str, Any]) -> None:
        entries = self._read()
        entries.append(entry)
        self._write(entries)

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        entries = self._read()
        if limit <= 0:
            return []
        return list(reversed(entries[-limit:]))
