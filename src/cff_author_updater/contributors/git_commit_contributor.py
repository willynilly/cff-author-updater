import logging

from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.managers.orcid_manager import OrcidManager

logger = logging.getLogger(__name__)

class GitCommitContributor(Contributor):

    def __init__(self, git_name: str, git_email: str, orcid_manager: OrcidManager):
        super().__init__()
        self.git_name: str = git_name
        self.git_email: str = git_email
        self.id = f"{self.git_name} <{self.git_email}>"
        
        self.is_valid_git_commit_contributor: bool = True

        if self.git_name and self.git_email:
            orcid = orcid_manager.search_orcid(full_name=self.git_name, email=self.git_email)
            if orcid and orcid_manager.validate_orcid(orcid):
                self.orcid = orcid
            elif orcid:
                logger.warning(
                    f"`{self.git_name}`: ORCID `{orcid}` is invalid or unreachable."
                )
            else:
                logger.info(f"`{self.git_name}`: No ORCID found.")

    def to_dict(self) -> dict:
        """
        Convert the Git Commit Contributor to a serializable dictionary representation.
        """
        return {
            "git_name": self.git_name,
            "git_email": self.git_email,
            "id": self.id,
        }
