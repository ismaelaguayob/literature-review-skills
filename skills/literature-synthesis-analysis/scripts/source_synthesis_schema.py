"""Structured output schema for source-level literature syntheses."""

from __future__ import annotations


SOURCE_SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source_group_id",
        "bib_key",
        "title",
        "source_kind",
        "relevance_to_review",
        "recommended_use",
        "confidence",
        "needs_deeper_review",
        "thesis",
        "key_concepts",
        "categories_suggested",
        "mechanisms_arguments_findings",
        "tensions_tradeoffs",
        "evidence_notes",
        "implications_for_review",
        "open_questions",
        "custom_sections",
        "semantic_audit",
    ],
    "properties": {
        "source_group_id": {"type": "string"},
        "bib_key": {"type": ["string", "null"]},
        "title": {"type": "string"},
        "source_kind": {"type": "string"},
        "relevance_to_review": {"type": "string", "enum": ["core", "supporting", "peripheral", "uncertain"]},
        "recommended_use": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "needs_deeper_review": {"type": "boolean"},
        "thesis": {"type": "string"},
        "key_concepts": {"type": "array", "items": {"type": "string"}},
        "categories_suggested": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["dimension", "category", "rationale", "trace"],
                "properties": {
                    "dimension": {"type": "string"},
                    "category": {"type": "string"},
                    "rationale": {"type": "string"},
                    "trace": {"type": "string"},
                },
            },
        },
        "mechanisms_arguments_findings": {"type": "array", "items": {"type": "string"}},
        "tensions_tradeoffs": {"type": "array", "items": {"type": "string"}},
        "evidence_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "evidence", "citation", "trace", "confidence"],
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {"type": "string"},
                    "citation": {"type": "string"},
                    "trace": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "implications_for_review": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "custom_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["heading", "content", "traces"],
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                    "traces": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "semantic_audit": {
            "type": "object",
            "additionalProperties": False,
            "required": ["extraction_quality", "possible_misreadings", "limits"],
            "properties": {
                "extraction_quality": {"type": "string", "enum": ["good", "mixed", "poor"]},
                "possible_misreadings": {"type": "array", "items": {"type": "string"}},
                "limits": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def openrouter_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "source_synthesis",
            "strict": True,
            "schema": SOURCE_SYNTHESIS_SCHEMA,
        },
    }
