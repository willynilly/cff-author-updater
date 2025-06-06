import logging
import re

from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.managers.github_manager import GitHubManager
from cff_author_updater.managers.orcid_manager import OrcidManager

GITHUB_USER_PROFILE_URL_REGEX = re.compile(
    r"^https:\/\/github\.com\/(?P<username>[a-zA-Z\d](?:[a-zA-Z\d]|-(?=[a-zA-Z\d])){0,38})$"
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
        self.name: str | None = None
        self.bio: str | None = None
        self.blog: str | None = None
        self.email: str | None = None
        self.is_organization: bool = False
        self.orcid: str | None = None

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
            self.name = user_profile_data.get("name", "")
            if self.name:
                self.name = self.name.strip()
            
            self.bio = user_profile_data.get("bio", "")
            if self.bio:
                self.bio = self.bio.strip()
        
            self.blog = user_profile_data.get("blog", "")    
            if self.blog:
                self.blog = self.blog.strip()

            self.email = user_profile_data.get("email", "")
            if self.email:
                self.email = self.email.strip()

            # Store organization flag
            self.is_organization = user_profile_data.get("type", "User") == "Organization"

        # Assign ORCID in priority order:
        # 1. Badge from profile
        orcid_manager: OrcidManager = github_manager.orcid_manager
        linked_orcid: str | None = orcid_manager.scrape_orcid_from_github_profile(self.github_username)
        if linked_orcid:
            self.orcid = linked_orcid
        elif self.blog:
            # 2. Blog field
            blog_orcid = orcid_manager.extract_orcid(self.blog)
            if blog_orcid:
                self.orcid = blog_orcid
            elif self.bio:
                # 3. Bio field
                bio_orcid = orcid_manager.extract_orcid(self.bio)
                if bio_orcid:
                    self.orcid = bio_orcid
                elif self.name and self.email:
                    #4. Name field (require at least first and last name) and Email
                    # If name is a single word, we cannot search for ORCID
                    name_parts: list[str] = self.name.split(" ", 1)
                    if len(name_parts) > 1:
                        if self.email:
                            # do not include the git name in the id when searching for the ORCID. Only search by email since they may have another name.
                            orcids: list[str] = orcid_manager.search_orcid(
                                name=None, email=self.email, return_url=True
                            )
                            if orcids:
                                self.orcid = orcids[0]
        if self.orcid and not orcid_manager.validate_orcid(orcid=self.orcid):
            logger.warning(
                f"@{self.github_username}: ORCID `{self.orcid}` is invalid or unreachable."
            )
        else:
            logger.info(f"@{self.github_username}: No ORCID found.")

    def to_dict(self) -> dict:
        """
        Convert the GitHubContributor to a serializable dictionary representation.
        """
        return {
            "github_username": self.github_username,
            "github_user_profile_url": self.github_user_profile_url,
            "id": self.id,
            "name": self.name,
            "bio": self.bio,
            "blog": self.blog,
            "email": self.email,
            "orcid": self.orcid,
            "is_organization": self.is_organization,
            "is_valid_github_user": self.is_valid_github_user,
        }
