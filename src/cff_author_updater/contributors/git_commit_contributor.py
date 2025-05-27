from cff_author_updater.contributors.contributor import Contributor


class GitCommitContributor(Contributor):

    def __init__(self, git_name: str, git_email):
        self.git_name: str = git_name
        self.git_email: str = git_email
        id = f"{self.git_name} <{self.git_email}>"
        super().__init__(id=id)
