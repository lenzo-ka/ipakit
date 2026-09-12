"""Shared admission for explicit token arrays, without tokenization or a model."""

from typing import cast


def validate_token_corpus(value: object) -> list[list[str]]:
    """Admit exact nonempty token strings; empty corpora and rows are valid.

    Operations separately declare population requirements and model membership.
    This is the existing comparison input shape, not a transcription codec.
    """
    if not isinstance(value, list):
        raise ValueError("a token corpus must be an explicit array of token arrays")
    for tokens in value:
        if not isinstance(tokens, list) or any(
            not isinstance(token, str) or not token for token in tokens
        ):
            raise ValueError(
                "each corpus entry must be an explicit array of nonempty token strings"
            )
    return cast(list[list[str]], value)
