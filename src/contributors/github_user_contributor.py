import re
from src.contributors.contributor import Contributor

GITHUB_USER_PROFILE_URL_REGEX = re.compile(
    r"^https:\/\/github\.com\/(?P<username>[a-zA-Z\d](?:[a-zA-Z\d]|-(?=[a-zA-Z\d])){0,38})$"
)


def is_github_user_profile_url(url: str) -> bool:
    return GITHUB_USER_PROFILE_URL_REGEX.match(url) is not None


def parse_github_username_from_github_profile_url(url: str) -> str | None:
    match = GITHUB_USER_PROFILE_URL_REGEX.match(url)
    return match.group("username") if match else None


class GitHubUserContributor(Contributor):

    def __init__(self, github_username: str):
        self.github_username: str = github_username
        self.github_profile_url: str = "https://github.com/" + self.github_username
        if not is_github_user_profile_url(self.github_profile_url):
            raise ValueError(
                "Cannot create GitHubUserContributor: invalid GitHub username."
            )

        super().__init__(id=self.github_profile_url)
