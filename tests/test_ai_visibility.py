from src.ai_visibility import mentioned


def test_mentioned_is_case_insensitive_and_word_bounded():
    names = ["ci-engineers", "ci engineers", "Sweco"]
    text = "Kijk eens naar CI-Engineers of sweco. Niet: swecoX."
    assert mentioned(text, names) == ["ci-engineers", "Sweco"]


def test_mentioned_empty_text():
    assert mentioned("", ["Sweco"]) == []


def test_ask_with_retry_retries_transient_then_succeeds():
    from src.ai_visibility import ask_with_retry, is_transient

    calls, sleeps = [], []

    def flaky(q):
        calls.append(q)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE: This model is currently experiencing high demand")
        return "Sweco en CI-Engineers"

    assert ask_with_retry(flaky, "vraag", sleep=sleeps.append) == "Sweco en CI-Engineers"
    assert len(calls) == 3 and sleeps == [5, 15]
    assert is_transient(RuntimeError("429 RESOURCE_EXHAUSTED")) and not is_transient(RuntimeError("404 NOT_FOUND"))


def test_ask_with_retry_no_retry_on_permanent_error():
    import pytest

    from src.ai_visibility import ask_with_retry

    calls = []

    def broken(q):
        calls.append(q)
        raise RuntimeError("404 NOT_FOUND. model niet beschikbaar")

    with pytest.raises(RuntimeError):
        ask_with_retry(broken, "vraag", sleep=lambda s: None)
    assert len(calls) == 1


def test_ask_with_retry_gives_up_after_attempts():
    import pytest

    from src.ai_visibility import ask_with_retry

    def always_busy(q):
        raise RuntimeError("503 UNAVAILABLE")

    with pytest.raises(RuntimeError):
        ask_with_retry(always_busy, "vraag", attempts=3, sleep=lambda s: None)
