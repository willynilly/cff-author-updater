from datetime import datetime


class Contribution:
    def __init__(self, id: str, created_at: datetime):
        self.id = id
        self.created_at: datetime = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
        }
