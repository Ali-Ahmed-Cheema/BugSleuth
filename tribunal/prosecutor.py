class Prosecutor:
    def analyze(self, evidence: list[dict], hypothesis: str, *, facts: list[dict] | None = None, mode: str = "user") -> dict:
        citations = [item["evidence"][0] for item in evidence if item.get("evidence")]
        evidence_ids = [fact["id"] for fact in (facts or [])[:5]]
        causal_chain = [
            "Incident evidence identifies an affected request or runtime condition.",
            "The cited code or change evidence identifies a candidate execution path.",
            "The candidate path is treated as a hypothesis until reproduction or stronger runtime evidence confirms it.",
        ]
        if mode == "demo":
            return {
                "agent": "Prosecutor",
                "argument": "The error began after deployment, the stack trace reaches payment validation, and commit abc1234 changed that condition. A zero-value request reproduces the exact error, forming a complete causal chain.",
                "citations": citations,
                "position": hypothesis,
                "evidence_ids": evidence_ids,
                "causal_chain": [
                    "A valid zero-value payment reaches payment validation.",
                    "The falsy condition treats 0 as missing.",
                    "Validation raises ValueError and the request fails.",
                ],
                "confidence_rationale": "Logs, source inspection, and a controlled reproduction converge on the same path.",
            }
        if not citations:
            return {
                "agent": "Prosecutor",
                "argument": "No evidence-supported root cause was identified. The repository was analyzed, but the actual incident evidence is missing or insufficient to justify a causal claim.",
                "citations": [],
                "position": "No active incident evidence identified",
                "evidence_ids": [],
                "causal_chain": [],
                "confidence_rationale": "No incident-specific evidence is available to support a causal claim.",
            }
        return {
            "agent": "Prosecutor",
            "argument": "The available evidence supports a specific code path or condition, but it remains provisional until it is connected to a reproducible failure or a confirmed error trace.",
            "citations": citations,
            "position": hypothesis,
            "evidence_ids": evidence_ids,
            "causal_chain": causal_chain,
            "confidence_rationale": "The cited facts are relevant but have not yet been connected to a controlled reproduction.",
        }
