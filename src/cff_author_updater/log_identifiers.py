from cff_author_updater.contributors.cff_author_contributor import CffAuthorContributor
from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import (
    GitHubContributor,
    parse_github_username_from_github_user_profile_url,
)


def create_identifier_of_contributor_for_logger(contributor: Contributor) -> str:
    """
    Returns a human-readable identifier string for this Contributor,
    used in logging skip decisions.
    """
    if isinstance(contributor, GitHubContributor):
        return f"@{contributor.github_username} (GitHub)"
    elif isinstance(contributor, GitCommitContributor):
        name = contributor.git_name or "unknown name"
        email = contributor.git_email or "unknown email"
        return f"{name} <{email}> (Git Commit)"
    else:
        return f"Unknown contributor type: {type(contributor).__name__}"
    
def create_identifier_of_cff_author_for_logger(cff_author: CffAuthorContributor) -> str:
    """
    Returns a human-readable identifier string for this CFF author,
    used in logging duplicate detection and other checks.
    """
    if cff_author is None:
        raise ValueError("Cannot create identifier for CFF Author: cff_author cannot be None.")

    a = cff_author.cff_author_data

    if "alias" in a:
        username = parse_github_username_from_github_user_profile_url(url=a["alias"])
        if username:
            return f"@{username} (GitHub)"
        else:
            return f"{a['alias']} (Alias)"
    elif "email" in a:
        return f"{a['email']} (Email)"
    elif "name" in a:
        return f"{a['name']} (Name)"
    else:
        raise ValueError("Cannot create identifier for CFF author: must have alias, email, or name.")
