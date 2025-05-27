class Contributor:

    def __init__(self, id: str):
        self.id = id
        self.contributions = []

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Contributor) and self.id == other.id

    @property
    def contributions_sorted_ascending_by_created_at(self):
        return sorted(self.contributions, key=lambda obj: (obj.created_at, obj.id))
