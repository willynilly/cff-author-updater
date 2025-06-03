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


class GitHubContributor(Contributor):

    def __init__(
        self,
        github_username: str,
        github_manager: GitHubManager
    ):
        super().__init__()
        
        orcid_manager: OrcidManager = github_manager.orcid_manager

        # Basic GitHub identity
        self.github_username: str = github_username.strip()
        self.github_user_profile_url: str = create_github_user_profile_url(self.github_username)

        if not is_github_user_profile_url(self.github_user_profile_url):
            raise ValueError(
                f"Cannot create GitHubContributor: invalid GitHub username `{self.github_username}`."
            )

        self.id: str = self.github_user_profile_url

        # Fetch profile data via GitHubManager
        user_profile_data: dict = github_manager.get_github_user_profile(self.github_username)

        # Store bio, blog, email
        self.bio: str = user_profile_data.get("bio", "").strip()
        self.blog: str = user_profile_data.get("blog", "").strip()
        self.email: str = user_profile_data.get("email", "").strip()

        # Store organization flag
        self.is_organization: bool = user_profile_data.get("type", "User") == "Organization"

        # Declare ORCID first
        self.orcid: str | None = None

        # Assign ORCID in priority order:
        # 1. Badge from profile
        linked_orcid = orcid_manager.scrape_orcid_from_github_profile(self.github_username)
        if linked_orcid:
            self.orcid = linked_orcid
        else:
            # 2. Blog field
            blog_orcid = orcid_manager.extract_orcid(self.blog)
            if blog_orcid:
                self.orcid = blog_orcid
            else:
                # 3. Bio field
                bio_orcid = orcid_manager.extract_orcid(self.bio)
                if bio_orcid:
                    self.orcid = bio_orcid

    def to_dict(self) -> dict:
        """
        Convert the GitHubContributor to a serializable dictionary representation.
        """
        return {
            "github_username": self.github_username,
            "github_user_profile_url": self.github_user_profile_url,
            "id": self.id,
            "bio": self.bio,
            "blog": self.blog,
            "email": self.email,
            "orcid": self.orcid,
            "is_organization": self.is_organization,
        }
