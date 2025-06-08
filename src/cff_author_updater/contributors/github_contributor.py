import logging

import regex  # Unicode-aware regex module

from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.managers.github_manager import GitHubManager
from cff_author_updater.managers.orcid_manager import OrcidManager

# Current GitHub OFFICIAL username rules: ASCII only
# Future-proof version: restrict to \p{L}\p{N} if needed later

GITHUB_USER_PROFILE_URL_REGEX = regex.compile(
    r"^https://github\.com/(?P<username>[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})$",
    flags=regex.IGNORECASE | regex.UNICODE
)

def is_github_user_profile_url(url: str) -> bool:
    return GITHUB_USER_PROFILE_URL_REGEX.match(url) is not None

def parse_github_username_from_github_user_profile_url(url: str) -> str | None:
    match = GITHUB_USER_PROFILE_URL_REGEX.match(url)
    return match.group("username") if match else None


def create_github_user_profile_url(github_username: str) -> str:
    """
    Create a GitHub profile URL from a GitHub username.
    """
    return "https://github.com/" + github_username

logger = logging.getLogger(__name__)

class GitHubContributor(Contributor):

    def __init__(
        self,
        github_username: str,
        github_manager: GitHubManager
    ):
        super().__init__()
        
        self.github_username: str = github_username.strip()
        self.github_user_profile_url: str = create_github_user_profile_url(self.github_username)
        self.id: str = self.github_user_profile_url
        self.github_name: str | None = None
        self.github_bio: str | None = None
        self.github_blog: str | None = None
        self.github_email: str | None = None
        self.github_is_organization: bool = False
        self.orcid: str | None = None
        self.orcid_name: str | None = None

        if is_github_user_profile_url(self.github_user_profile_url):
            self.is_valid_github_user = True
        else:
            logger.error(f"Cannot create GitHubContributor: invalid GitHub username `{self.github_username}`.")
            self.is_valid_github_user = False
            return

        # Fetch profile data via GitHubManager
        user_profile_data: dict | None = github_manager.get_github_user_profile(self.github_username)
        if not user_profile_data:
            self.is_valid_github_user = False
        else:
            # Store name, bio, blog, email
            self.github_name = user_profile_data.get("name", "")
            if self.github_name:
                self.github_name = self.github_name.strip()
            
            self.github_bio = user_profile_data.get("bio", "")
            if self.github_bio:
                self.github_bio = self.github_bio.strip()
        
            self.github_blog = user_profile_data.get("blog", "")    
            if self.github_blog:
                self.github_blog = self.github_blog.strip()

            self.github_email = user_profile_data.get("email", "")
            if self.github_email:
                self.github_email = self.github_email.strip()

            # Store organization flag
            self.github_is_organization = user_profile_data.get("type", "User") == "Organization"

        # Assign ORCID in priority order:
        orcid_manager: OrcidManager = github_manager.orcid_manager

        if not self.orcid and self.github_username:
            # 1. Badge from profile
            linked_orcid: str | None = orcid_manager.scrape_orcid_from_github_profile(github_username=self.github_username)
            if linked_orcid:
                self.orcid = linked_orcid

        if not self.orcid and self.github_blog:
            # 2. Blog field
            blog_orcid = orcid_manager.extract_orcid(self.github_blog, find_url=True, return_url=True)
            if blog_orcid:
                self.orcid = blog_orcid
        
        if not self.orcid and self.github_bio:
            # 3. Bio field
            bio_orcid = orcid_manager.extract_orcid(self.github_bio, find_url=True, return_url=True)
            if bio_orcid:
                self.orcid = bio_orcid
                
        if not self.orcid and self.github_email:
            #4. Search Orcid by Email
            # do not include the git name in the id when searching for the ORCID. Only search by email since they may have another name.
            orcids: list[str] = orcid_manager.search_orcid(
                name=None, email=self.github_email, return_url=True
            )
            if orcids:
                self.orcid = orcids[0]
        
        if not self.orcid:
            logger.info(f"@{self.github_username}: No ORCID found.")
        elif not orcid_manager.validate_orcid(orcid=self.orcid):
            logger.warning(
                f"@{self.github_username}: ORCID `{self.orcid}` is invalid or unreachable."
            )
        else:
            if not self.orcid_name:
                orcid_names, credit_name, combined_credit_name, other_names = orcid_manager.get_names_from_orcid(orcid=self.orcid)
                if orcid_names:
                    orcid_name = credit_name or combined_credit_name or orcid_names[0]
                    if not self.orcid_name:
                        self.orcid_name = orcid_name
                    if self.github_name:
                        # Check if the ORCID name matches the GitHub name
                        if self.orcid_name != self.github_name:
                            logger.warning(
                                f"`{self.github_email}`: ORCID name `{self.orcid_name}` does not match GitHub name `{self.github_name}` Using GitHub name."
                            )
                    else:
                        logger.info(f"`{self.github_email}`: Added name `{self.orcid_name}` from ORCID `{self.orcid}`.")    
                
                


    def to_dict(self) -> dict:
        """
        Convert the GitHubContributor to a serializable dictionary representation.
        """
        return {
            "id": self.id,
            "github_username": self.github_username,
            "github_user_profile_url": self.github_user_profile_url,
            "github_name": self.github_name,
            "github_bio": self.github_bio,
            "github_blog": self.github_blog,
            "github_email": self.github_email,
            "github_is_organization": self.github_is_organization,
            "orcid": self.orcid,
            "orcid_name": self.orcid_name,
            "is_valid_github_user": self.is_valid_github_user,
        }
