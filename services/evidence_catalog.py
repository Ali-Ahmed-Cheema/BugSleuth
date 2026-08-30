"""Create an auditable, source-labelled catalogue from investigator output."""

from __future__ import annotations

import re


_CITATION = re.compile(r"^(?P<file>.+?):(?P<line>\d+):\s*(?P<excerpt>.*)$")


def build_evidence_catalog(investigators: list[dict]) -> list[dict]:
    """Return deterministic ``E-NNN`` facts without adding interpretation."""
    facts: list[dict] = []
    for investigator in investigators:
        if investigator.get("status") != "complete":
            continue
        agent = investigator.get("agent", "Investigator")
        for raw in investigator.get("evidence", []):
            text = str(raw).strip()
            if not text:
                continue
            match = _CITATION.match(text)
            source_file = match.group("file") if match else agent
            line = int(match.group("line")) if match else None
            excerpt = match.group("excerpt") if match else text
            source_type = _source_type(agent)
            facts.append({
                "id": f"E-{len(facts) + 1:03d}",
                "type": source_type,
                "attribution": "FACT",
                "investigator": agent,
                "source": source_file,
                "line": line,
                "excerpt": excerpt,
                "description": f"Extracted by {agent} from supplied evidence.",
            })
    return facts


def _source_type(agent: str) -> str:
    if agent == "Log Investigator":
        return "log"
    if agent == "Change Investigator":
        return "git"
    if agent == "Code Investigator":
        return "source"
    if agent == "Pipeline Investigator":
        return "pipeline"
    if agent == "Deployment Context Investigator":
        return "deployment"
    return "other"
