import json
from pathlib import Path
from typing import Any


class WarningRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text('{"last_id": 0, "warnings": {}}', encoding='utf-8')

    def _load(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding='utf-8').strip()
            if not raw:
                return {'last_id': 0, 'warnings': {}}
            data = json.loads(raw)
            if isinstance(data, dict):
                data.setdefault('last_id', 0)
                data.setdefault('warnings', {})
                return data
        except Exception:
            pass
        return {'last_id': 0, 'warnings': {}}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def add_warning(self, user_id: int, moderator_id: int, reason: str, timestamp: str) -> dict[str, Any]:
        data = self._load()
        data['last_id'] = int(data.get('last_id', 0)) + 1
        warning = {
            'id': data['last_id'],
            'moderator_id': moderator_id,
            'reason': reason,
            'timestamp': timestamp,
        }
        warnings = data.setdefault('warnings', {})
        user_key = str(user_id)
        user_warnings = warnings.setdefault(user_key, [])
        user_warnings.append(warning)
        self._save(data)
        return warning

    def get_warnings(self, user_id: int) -> list[dict[str, Any]]:
        data = self._load()
        warnings = data.get('warnings', {})
        user_warnings = warnings.get(str(user_id), [])
        if not isinstance(user_warnings, list):
            return []
        return [item for item in user_warnings if isinstance(item, dict)]

    def remove_warning(self, user_id: int, warning_id: int) -> dict[str, Any] | None:
        data = self._load()
        warnings = data.get('warnings', {})
        user_key = str(user_id)
        user_warnings = warnings.get(user_key, [])
        if not isinstance(user_warnings, list):
            return None

        removed: dict[str, Any] | None = None
        kept: list[dict[str, Any]] = []
        for item in user_warnings:
            if not isinstance(item, dict):
                continue
            if removed is None and int(item.get('id', -1)) == warning_id:
                removed = item
                continue
            kept.append(item)

        if removed is None:
            return None

        if kept:
            warnings[user_key] = kept
        else:
            warnings.pop(user_key, None)
        self._save(data)
        return removed
