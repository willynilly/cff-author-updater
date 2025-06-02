from cff_author_updater.contributors.contributor import Contributor


class GitCommitContributor(Contributor):

    def __init__(self, git_name: str, git_email):
        super().__init__()
        self.git_name: str = git_name
        self.git_email: str = git_email
        self.id = f"{self.git_name} <{self.git_email}>"

    def to_dict(self) -> dict:
        """
        Convert the Git Commit Contributor to a serializable dictionary representation.
        """
        return {
            "git_name": self.git_name,
            "git_email": self.git_email,
            "id": self.id,
        }
