"""Shared validation helpers for domain models."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MAX_TEXT_LENGTH = 20_000
MAX_SHORT_TEXT_LENGTH = 500
MAX_LIST_ITEMS = 20
MAX_METADATA_KEYS = 50

BoundedText = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=MAX_TEXT_LENGTH
    ),
]
OptionalBoundedText = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, max_length=MAX_TEXT_LENGTH),
]
ShortText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_SHORT_TEXT_LENGTH,
    ),
]
StringList = Annotated[
    list[ShortText], Field(default_factory=list, max_length=MAX_LIST_ITEMS)
]

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
JsonObject = Annotated[
    dict[str, JsonValue],
    Field(default_factory=dict, max_length=MAX_METADATA_KEYS),
]


class DomainModel(BaseModel):
    """Base class for immutable public domain models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
