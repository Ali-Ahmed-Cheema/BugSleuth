"""Validate the portable trust-layer contract returned by investigations."""

from __future__ import annotations

from jsonschema import Draft7Validator


TRUST_LAYER_SCHEMA = {
    "type": "object",
    "required": ["facts", "hypothesis", "tribunal", "verification"],
    "properties": {
        "facts": {"type": "array", "items": {"type": "object", "required": ["id", "type", "attribution", "source"]}},
        "hypothesis": {"type": "object", "required": ["id", "statement", "evidence_ids", "causal_chain"]},
        "tribunal": {"type": "object", "required": ["prosecutor", "defense", "judge"]},
        "verification": {"type": "object", "required": ["status", "execution_policy"]},
    },
}


def validate_trust_layer(trust_layer: dict) -> list[str]:
    return [error.message for error in Draft7Validator(TRUST_LAYER_SCHEMA).iter_errors(trust_layer)]
