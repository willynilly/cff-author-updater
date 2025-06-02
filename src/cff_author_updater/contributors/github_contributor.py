import re

from cff_author_updater.contributors.contributor import Contributor

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

    def __init__(self, github_username: str):
        super().__init__()
        self.github_username: str = github_username
        self.github_user_profile_url: str = create_github_user_profile_url(self.github_username)
        if not is_github_user_profile_url(self.github_user_profile_url):
            raise ValueError(
                "Cannot create GitHubContributor: invalid GitHub username."
            )
        self.id: str = self.github_user_profile_url

    def to_dict(self) -> dict:
        """
        Convert the GitHubContributor to a serializable dictionary representation.
        """
        return {
            "git_name": self.github_username,
            "git_email": self.github_user_profile_url,
            "id": self.id,
        }
