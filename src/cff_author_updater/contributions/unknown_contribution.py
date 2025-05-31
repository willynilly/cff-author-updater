from datetime import datetime

from cff_author_updater.contributions.contribution import Contribution


class UnknownContribution(Contribution):

    def __init__(
        self,
        id: str,
        created_at: datetime | None = None,
    ):
        if created_at is None:
            # make this the minimum time by default so that it comes first when sorting contributions
            created_at = datetime.min
        super().__init__(id=id, created_at=created_at)
