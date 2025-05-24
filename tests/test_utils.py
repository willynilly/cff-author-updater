import pytest

from utils import add_more_contribution_details


@pytest.fixture
def contribution_details():
    return {
        "user1": {
            "commits": ["some_sha1", "another_sha1"],
            "issues": ["some_issue_url", "another_issue_url"],
            "reviews": ["some_review_url", "another_review_url"],
            "pr_comments": ["some_pr_comment_url"],
        }
    }


@pytest.fixture
def more_contribution_details():
    return {
        "user1": {
            "issue_comments": ["some_issue_comment_url", "another_issue_comment_url"],
            "pr_comments": ["another_pr_comment_url"],
        }
    }


@pytest.fixture
def combined_contribution_details():
    return {
        "user1": {
            "commits": ["some_sha1", "another_sha1"],
            "issues": ["some_issue_url", "another_issue_url"],
            "reviews": ["some_review_url", "another_review_url"],
            "issue_comments": ["some_issue_comment_url", "another_issue_comment_url"],
            "pr_comments": ["some_pr_comment_url", "another_pr_comment_url"],
        }
    }


def test_add_more_contribution_details(
    contribution_details, more_contribution_details, combined_contribution_details
):
    actual = add_more_contribution_details(
        contribution_details=contribution_details,
        more_contribution_details=more_contribution_details,
    )
    assert actual == combined_contribution_details
