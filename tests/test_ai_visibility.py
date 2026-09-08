from src.ai_visibility import mentioned


def test_mentioned_is_case_insensitive_and_word_bounded():
    names = ["ci-engineers", "ci engineers", "Sweco"]
    text = "Kijk eens naar CI-Engineers of sweco. Niet: swecoX."
    assert mentioned(text, names) == ["ci-engineers", "Sweco"]


def test_mentioned_empty_text():
    assert mentioned("", ["Sweco"]) == []
