import pytest

from cff_author_updater.contributors.cff_author_contributor import CffAuthorContributor


def test_contructor_with_empty_data():
    with pytest.raises(ValueError) as e:
        a: CffAuthorContributor = CffAuthorContributor(cff_author_data={})
    assert "Unknown CFF Author Type" in str(e.value)


def test_contructor_with_none_as_data():
    with pytest.raises(ValueError) as e:
        a: CffAuthorContributor = CffAuthorContributor(cff_author_data=None)  # type: ignore
    assert "Invalid CFF author data" in str(e.value)


def test_contructor_with_valid_data_using_orcid():
    cff_author_data = {
        "name": "John Doe",
        "orcid": "0000-0000-0000-0000",
        "email": "something@something.nl",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert a.id == "0000-0000-0000-0000"


def test_contructor_with_valid_data_using_email():
    cff_author_data = {"name": "John Doe", "email": "something@something.nl"}
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert a.id == "something@something.nl"


def test_contructor_with_valid_data_using_name_and_email_and_github_alias():
    cff_author_data = {
        "name": "Will Riley",
        "email": "sombody@somebody.nl",
        "alias": "https://github.com/willynilly",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert (
        a.id == "https://github.com/willynilly"
    )  # The alias is a GitHub profile URL and has higher priority than email or name for id, so it should be used as the ID


def test_contructor_with_valid_data_using_name_github_alias_and_orcid():
    cff_author_data = {
        "name": "Will Riley",
        "orcid": "0000-0000-0000-0000",
        "alias": "https://github.com/willynilly",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert (
        a.id == "0000-0000-0000-0000"
    )  # It has an ORCID and and ORCID has higher priority than github alias and name for id, so ORCID should be used as the ID


def test_contructor_with_valid_data_using_name_and_non_github_alias():
    cff_author_data = {
        "name": "Will Riley",
        "alias": "willynils",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert (
        a.id == "Will Riley"
    )  # The alias is not a GitHub profile URL, so it should fallback to the name


def test_contructor_with_valid_data_using_given_and_family_names():
    cff_author_data = {
        "given-names": "Will",
        "family-names": "Riley",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert a.id == "Will Riley"


def test_contructor_with_valid_data_using_name():
    cff_author_data = {
        "name": "Will Riley",
    }
    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data)
    assert a.id == "Will Riley"


def test_set_membership_different_with_is_same_author_when_using_same_name_but_different_email():
    cff_author_data_a = {"name": "Will Riley", "email": "something@something.nl"}
    cff_author_data_b = {"name": "Bill Riley", "email": "something@something.nl"}

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)
    is_same = a.is_same_author(b)
    assert is_same  # They have the same email, so they should be considered the same contributor

    s: set = set()
    s.add(a)
    assert a in s
    assert (
        b not in s
    )  # b has a different name so it should not be in the set because the objects are hashed with all their data
    s.add(b)
    assert len(s) == 2  # Should have two unique contributor


def test_is_same_using_same_name_and_different_orcid():
    cff_author_data_a = {"name": "Will Riley", "orcid": "0000-0000-0000-0000"}
    cff_author_data_b = {"name": "Will Riley", "orcid": "1111-1111-1111-1111"}

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)
    is_same = a.is_same_author(b)
    assert is_same  # They have different ORCIDs, but same names, so they should be considered the same author


def test_is_same_using_different_name_and_different_orcid():
    cff_author_data_a = {"name": "Will Riley", "orcid": "0000-0000-0000-0000"}
    cff_author_data_b = {"name": "Bill Riley", "orcid": "1111-1111-1111-1111"}

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)
    is_same = a.is_same_author(b)
    assert (
        not is_same
    )  # They have different ORCIDs and different names, so they should not be considered the same author


def test_is_same_using_same_cff_entity_full_name_and_same_cff_person_full_name_and_different_email():
    cff_author_data_a = {"name": "Will Riley", "email": "somebody1@somebody.nl"}
    cff_author_data_b = {
        "given-names": "Will",
        "family-names": "Riley",
        "email": "somebody2@somebody.nl",
    }

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)
    is_same = a.is_same_author(b)
    assert is_same  # They have different emails, but same full names, so they should be considered the same author


def test_is_same_using_different_cff_entity_full_name_and_same_cff_person_full_name_and_different_email():
    cff_author_data_a = {"name": "Will Riley", "email": "somebody1@somebody.nl"}
    cff_author_data_b = {
        "given-names": "Bill",
        "family-names": "Riley",
        "email": "somebody2@somebody.nl",
    }

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)
    is_same = a.is_same_author(b)
    assert (
        not is_same
    )  # They have different emails, but same full names, so they should be considered the same author


def test_set_membership_using_same_name_and_different_orcid():
    cff_author_data_a = {"name": "Will Riley", "orcid": "0000-0000-0000-0000"}
    cff_author_data_b = {"name": "Will Riley", "orcid": "1111-1111-1111-1111"}

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)

    s: set = set()
    s.add(a)
    assert a in s
    assert b not in s  # b has a different ORCID, so it should not be in the set
    s.add(b)
    assert len(s) == 2  # Should have two unique contributors


def test_set_membership_using_different_name_and_different_orcid():
    cff_author_data_a = {"name": "Will Riley", "orcid": "0000-0000-0000-0000"}
    cff_author_data_b = {"name": "Bill Riley", "orcid": "1111-1111-1111-1111"}

    a: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_a)
    b: CffAuthorContributor = CffAuthorContributor(cff_author_data=cff_author_data_b)

    s: set = set()
    s.add(a)
    assert a in s
    assert (
        b not in s
    )  # b has a different ORCID and different name, so it should not be in the set
    s.add(b)
    assert len(s) == 2  # Should have two unique contributors
