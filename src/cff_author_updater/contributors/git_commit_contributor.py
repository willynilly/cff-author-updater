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
        self.orcid: str | None = None
        self.orcid_name: str | None = None

        if self.git_email:
            # do not include the git name in the id when searching for the ORCID. Only search by email since they may have another name.
            orcids: list[str] = orcid_manager.search_orcid(name=None, email=self.git_email, return_url=True)
            
            if not orcids:
                logger.info(f"`{self.git_email}`: No ORCID found.")
            elif orcid_manager.validate_orcid(orcids[0], is_url=True):
                self.orcid = orcids[0]
                orcid_names, credit_name, combined_credit_name, other_names = orcid_manager.get_names_from_orcid(orcid=self.orcid)
                if orcid_names:
                    orcid_name = credit_name or combined_credit_name or orcid_names[0]
                    if not self.orcid_name:
                        self.orcid_name = orcid_name
                    if self.git_name:
                        # Check if the ORCID name matches the git name
                        if self.orcid_name != self.git_name:
                            logger.warning(
                                f"`{self.git_email}`: ORCID name `{self.orcid_name}` does not match git name `{self.git_name}` Using git name."
                            )
                    else:
                        logger.info(f"`{self.git_email}`: Added name `{self.orcid_name}` from ORCID `{self.orcid}`.")    
                    
            else:
                logger.warning(
                    f"`{self.git_name}`: ORCID `{orcids[0]}` is invalid or unreachable."
                )

    def to_dict(self) -> dict:
        """
        Convert the Git Commit Contributor to a serializable dictionary representation.
        """
        return {
            "git_name": self.git_name,
            "git_email": self.git_email,
            "orcid": self.orcid,
            "orcid_name": self.orcid_name,
            "id": self.id,
        }
