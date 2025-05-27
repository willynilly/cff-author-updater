import os


class Flags:

    flags: dict[str, bool] = {
        "authorship_for_pr_commits": os.environ.get(
            "AUTHORSHIP_FOR_PR_COMMITS", "true"
        ).casefold()
        == "true",
        "authorship_for_pr_reviews": os.environ.get(
            "AUTHORSHIP_FOR_PR_REVIEWS", "true"
        ).casefold()
        == "true",
        "authorship_for_pr_issues": os.environ.get(
            "AUTHORSHIP_FOR_PR_ISSUES", "true"
        ).casefold()
        == "true",
        "author_ship_for_pr_issue_comments": os.environ.get(
            "AUTHORSHIP_FOR_PR_ISSUE_COMMENTS", "true"
        ).casefold()
        == "true",
        "authorship_for_pr_comments": os.environ.get(
            "AUTHORSHIP_FOR_PR_COMMENT", "true"
        ).casefold()
        == "true",
        "post_pr_comment": os.environ.get("POST_PR_COMMENT", "true").casefold()
        == "true",
        "missing_author_invalidates_pr": os.environ.get(
            "MISSING_AUTHOR_INVALIDATES_PR", "true"
        ).casefold()
        == "true",
    }

    @classmethod
    def has(cls, key) -> bool:
        return cls.flags.get(key, False)
