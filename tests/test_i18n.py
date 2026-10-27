import string

import pytest

from aqj import i18n


def fields(text: str) -> set[str]:
    names = {name for _, name, _, _ in string.Formatter().parse(text) if name}
    # "{attempts}" is derived from "{n}", so the two are interchangeable
    return {"n" if name == "attempts" else name for name in names}


@pytest.mark.parametrize("key", sorted(i18n.STRINGS))
def test_every_string_is_translated_with_the_same_placeholders(key):
    en, uk = i18n.STRINGS[key]
    assert en.strip() and uk.strip()
    assert fields(en) == fields(uk), key


def test_no_exclamation_marks():
    for en, uk in i18n.STRINGS.values():
        assert "!" not in en and "!" not in uk


@pytest.mark.parametrize(
    "n, expected",
    [
        (1, "1 спроба"),
        (2, "2 спроби"),
        (4, "4 спроби"),
        (5, "5 спроб"),
        (11, "11 спроб"),
        (12, "12 спроб"),
        (21, "21 спроба"),
        (22, "22 спроби"),
        (111, "111 спроб"),
    ],
)
def test_ukrainian_plural(n, expected):
    i18n.set_language("uk")
    try:
        assert i18n.attempts(n) == expected
    finally:
        i18n.set_language("en")


def test_english_plural_and_tr():
    i18n.set_language("en")
    assert i18n.attempts(1) == "1 attempt"
    assert i18n.attempts(3) == "3 attempts"
    assert i18n.tr("state.success", n=3) == "Got in after 3 attempts"


def test_key_param_does_not_clash():
    i18n.set_language("en")
    assert "F6" in i18n.tr("set.key_taken", key="F6")


def test_unknown_language_falls_back_to_english():
    assert i18n.set_language("de") == "en"
    assert i18n.set_language("system") in ("en", "uk")
