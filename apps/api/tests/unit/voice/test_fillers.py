import pytest

from app.voice.fillers import FILLER_TOKENS, is_filler


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("um", True),
        ("Uh,", True),
        ("Um.", True),
        ("UHM", True),
        ("like", False),
        ("Kubernetes", False),
        ("", False),
    ],
)
def test_is_filler_token_matching(token: str, expected: bool) -> None:
    assert is_filler(token) is expected


def test_provider_flag_true_overrides_token_lookup() -> None:
    assert is_filler("Kubernetes", provider_flag=True) is True


def test_provider_flag_false_overrides_token_lookup() -> None:
    assert is_filler("um", provider_flag=False) is False


def test_provider_flag_none_falls_back_to_token_lookup() -> None:
    assert is_filler("um", provider_flag=None) is True
    assert is_filler("like", provider_flag=None) is False


def test_filler_tokens_is_a_frozenset_of_lowercase_words() -> None:
    assert isinstance(FILLER_TOKENS, frozenset)
    assert all(token == token.lower() for token in FILLER_TOKENS)
    assert "um" in FILLER_TOKENS
    assert "like" not in FILLER_TOKENS
