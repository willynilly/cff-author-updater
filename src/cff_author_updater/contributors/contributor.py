class Contributor:

    def to_dict(self) -> dict:
        return {}

    def __hash__(self):
        """
        Return a hash based on its to_dict().
        This allows it to be used in sets and as dictionary keys.
        """
        return hash(str(self.to_dict()))

    def __eq__(self, other):

        return type(other) is type(self) and str(self.to_dict()) == str(other.to_dict())
