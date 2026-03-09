import json
from pathlib import Path


class PanelStateRepository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def get(self, key: str):
        return self.load().get(key)

    def set(self, key: str, value) -> None:
        data = self.load()
        data[key] = value
        self.save(data)
