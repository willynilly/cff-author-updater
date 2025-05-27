class Contributor:

    def __init__(self, id: str):
        self.id = id
        # self.contributions = []

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Contributor) and self.id == other.id

    def __str__(self):
        return str(self.id)

    def to_dict(self):
        return {"id": self.id}
