"""Extract exactly one top-level JSON object from model text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from prompt_orchestrator.exceptions import StructuredOutputError


@dataclass(frozen=True)
class ExtractedJsonObject:
    """JSON object text and its offsets in the source text."""

    text: str
    start: int
    end: int


def strip_markdown_json_fence(text: str) -> str:
    """Remove one enclosing Markdown code fence when it wraps the whole output."""
    stripped = text.strip()
    if not stripped.startswith("```") or not stripped.endswith("```"):
        return text

    lines = stripped.splitlines()
    if len(lines) < 2:
        return text
    opening = lines[0].strip().lower()
    if opening not in {"```", "```json"}:
        return text
    if lines[-1].strip() != "```":
        return text
    return "\n".join(lines[1:-1]).strip()


def extract_json_object_text(text: str) -> ExtractedJsonObject:
    """Extract exactly one top-level JSON object, allowing limited surrounding prose."""
    unfenced = strip_markdown_json_fence(text)
    candidates = _find_balanced_object_candidates(unfenced)
    if not candidates:
        raise StructuredOutputError(
            "No complete top-level JSON object was found.",
            code="STRUCTURED_JSON_NOT_FOUND",
        )
    if len(candidates) > 1:
        raise StructuredOutputError(
            "Multiple top-level JSON objects were found.",
            code="STRUCTURED_JSON_AMBIGUOUS",
        )
    return candidates[0]


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract and parse exactly one top-level JSON object."""
    extracted = extract_json_object_text(text)
    try:
        parsed = json.loads(extracted.text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            f"JSON parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            code="STRUCTURED_JSON_PARSE_ERROR",
        ) from exc
    if not isinstance(parsed, dict):
        raise StructuredOutputError(
            "Structured output must be a JSON object.",
            code="STRUCTURED_JSON_NOT_OBJECT",
        )
    return parsed


def _find_balanced_object_candidates(text: str) -> list[ExtractedJsonObject]:
    candidates: list[ExtractedJsonObject] = []
    in_string = False
    escaped = False
    depth = 0
    start: int | None = None

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(
                    ExtractedJsonObject(
                        text=text[start : index + 1], start=start, end=index + 1
                    )
                )
                start = None

    return candidates
