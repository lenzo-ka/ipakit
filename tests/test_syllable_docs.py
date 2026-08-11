"""The counts and disagreement reported by docs/syllabification.md."""

import ipakit


def _totals(language, forms):
    results = [ipakit.syllabify(form, language) for form in forms]
    return sum(len(r.syllables) for r in results), sum(
        len(r.conflicts) for r in results
    )


def test_japanese_report_counts() -> None:
    forms = ("pen", "hotːo", "toːkjo", "ko͜i")
    results = [ipakit.syllabify(form, "japanese") for form in forms]
    assert (len(forms), sum(len(r.syllables) for r in results)) == (4, 6)
    assert sum(len(r.morae) for r in results) == 9
    assert sum(len(r.conflicts) for r in results) == 0


def test_mandarin_report_counts() -> None:
    forms = ("ma˥ma˨˩˦", "xau", "ʈ͡ʂʊŋkuɔ")
    assert (len(forms), *_totals("mandarin", forms)) == (3, 5, 0)
    assert ipakit.syllabify("mla", "mandarin").unsyllabified == ((0, 3),)


def test_spanish_report_counts_and_conflict() -> None:
    forms = ("kasa", "atɾas", "poeta", "los‿otɾos", "at.ɾa")
    assert (len(forms), *_totals("spanish", forms)) == (5, 12, 1)


def test_three_languages_disagree_on_one_form() -> None:
    answers = {
        language: ipakit.syllabify("atɾa", language).spelled()
        for language in ("japanese", "mandarin", "spanish")
    }
    assert answers == {
        "japanese": ("a", "ɾa"),
        "mandarin": (),
        "spanish": ("a", "tɾa"),
    }
    assert ipakit.syllabify("atɾa", "japanese").unsyllabified == ((1, 2),)
