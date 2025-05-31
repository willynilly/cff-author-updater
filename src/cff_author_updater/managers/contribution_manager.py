from cff_author_updater.contributions.contribution import Contribution
from cff_author_updater.contributors.contributor import Contributor
from collections import defaultdict


class ContributionManager:

    def __init__(self):
        self._contributions: list[Contribution] = []
        self._contributions_by_contributor: dict[Contributor, list[Contribution]] = {}
        self._contributors_by_contribution: dict[Contribution, list[Contributor]] = {}

    def add_contribution(self, contribution: Contribution, contributor: Contributor):
        if not isinstance(contributor, Contributor):
            raise ValueError(
                "Cannot add contribution: contributor must be a Contributor instance"
            )
        if not isinstance(contribution, Contribution):
            raise ValueError(
                "Cannot add contribution: contribution must be a Contribution instance"
            )

        if contribution not in self._contributions:
            self._contributions.append(contribution)

        if contributor not in self._contributions_by_contributor:
            self._contributions_by_contributor[contributor] = []
        if contribution not in self._contributions_by_contributor[contributor]:
            self._contributions_by_contributor[contributor].append(contribution)
            self._contributions_by_contributor[contributor].sort(
                key=lambda x: x.created_at
            )

        if contribution not in self._contributors_by_contribution:
            self._contributors_by_contribution[contribution] = []
        if contributor not in self._contributors_by_contribution[contribution]:
            self._contributors_by_contribution[contribution].append(contributor)

    @property
    def contributors(self) -> list[Contributor]:
        return list(self._contributions_by_contributor.keys())

    @property
    def contributors_sorted_by_first_contribution(self) -> list[Contributor]:
        contributor_and_first_contribution_tuple_list: list[
            tuple[Contributor, Contribution]
        ] = []
        for contributor in self._contributions_by_contributor.keys():
            if len(self._contributions_by_contributor[contributor]) > 0:
                first_contribution: Contribution = self._contributions_by_contributor[
                    contributor
                ][0]
                contributor_and_first_contribution_tuple_list.append(
                    (contributor, first_contribution)
                )

        contributor_and_first_contribution_tuple_list.sort(
            key=lambda x: x[1].created_at
        )
        return [x[0] for x in contributor_and_first_contribution_tuple_list]

    def get_contributions_for(self, contributor: Contributor) -> list[Contribution]:
        return self._contributions_by_contributor.get(contributor, [])

    def get_contribution_categories_for(
        self, contributor: Contributor
    ) -> dict[str, list[Contribution]]:
        contributions = self.get_contributions_for(contributor)
        categories = defaultdict(list)
        for contribution in contributions:
            categories[contribution.__class__.__name__].append(contribution)
        return dict(categories)

    def to_dict(self) -> list[dict]:
        result = []
        for contributor in self.contributors_sorted_by_first_contribution:
            contributions_by_category = self.get_contribution_categories_for(
                contributor
            )
            result.append(
                {
                    "contributor": contributor.to_dict(),
                    "contributions": {
                        category: [c.id for c in contrib_list]
                        for category, contrib_list in contributions_by_category.items()
                    },
                }
            )
        return result

    def merge(self, other: "ContributionManager"):
        for contributor in other._contributions_by_contributor:
            for contribution in other._contributions_by_contributor[contributor]:
                self.add_contribution(contribution, contributor)

    def __len__(self):
        return len(self._contributions_by_contributor)
