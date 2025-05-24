def add_more_contribution_details(
    contribution_details, more_contribution_details
) -> dict:
    for contributor, contributions_by_category in more_contribution_details.items():
        for contribution_category, contributions in contributions_by_category.items():
            contribution_details.setdefault(contributor, {})
            old_contributions = contribution_details[contributor].get(
                contribution_category, []
            )
            contribution_details[contributor][contribution_category] = (
                old_contributions + contributions
            )
    return contribution_details
