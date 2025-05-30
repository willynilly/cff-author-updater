from cff_author_updater.contributors.contributor import Contributor


def test_to_dict():
    c: Contributor = Contributor()
    assert c.to_dict() == {}


def test_contributor_set_membership():
    c1: Contributor = Contributor()
    c2: Contributor = Contributor()

    s: set = set()
    s.add(c1)
    assert c1 in s
    assert c2 in s  # c2 should have the same hash so it should be in teh set
    assert len(s) == 1  # Should only have one unique contributor


def test_hash():
    c1: Contributor = Contributor()
    assert c1.__hash__() == hash("{}")
