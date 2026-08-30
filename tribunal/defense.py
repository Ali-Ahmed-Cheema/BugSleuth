class Defense:
    def analyze(self, evidence: list[dict], alternatives: list[str], *, facts: list[dict] | None = None, mode: str = "user") -> dict:
        evidence_ids = [fact["id"] for fact in (facts or [])]
        if mode == "demo":
            return {
                "agent": "Defense",
                "argument": "Database latency and deployment configuration remain plausible alternatives, but the available evidence does not show a database timeout or routing failure. The strongest challenge is to reproduce the request without either dependency.",
                "alternatives": alternatives[1:],
                "missing_evidence": ["A production replay or metrics export would further strengthen timing correlation."],
                "challenges": [{
                    "evidence_id": evidence_ids[0] if evidence_ids else "UNAVAILABLE",
                    "argument": "The demo proves the validation behaviour, but a controlled demonstration is not identical to production traffic.",
                    "gap": "Production request telemetry and the payment API contract are still needed to establish the full business context.",
                }],
            }
        missing = [
            "Application logs or stack trace evidence tied to the reported failure.",
            "A failing test or reproduction path that matches the incident.",
            "Operational context that confirms whether the problem is runtime, configuration, or code related."
        ]
        return {
            "agent": "Defense",
            "argument": "The current evidence does not yet prove a root cause. The investigation remains limited by missing logs, stack traces, failing tests, or runtime context.",
            "alternatives": [alt for alt in alternatives if alt.lower() != "the available evidence points to a defect in the application code."],
            "missing_evidence": missing,
            "challenges": [{
                "evidence_id": evidence_ids[0] if evidence_ids else "UNAVAILABLE",
                "argument": "The current facts may be correlated with the incident without proving that they caused it.",
                "gap": missing[0],
            }],
        }
