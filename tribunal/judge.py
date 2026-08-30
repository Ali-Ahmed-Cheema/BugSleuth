class Judge:
    def _make_verdict(self, *, verdict: str, confidence: float, leading_hypothesis: str, reason: str, evidence_supporting: list[str], evidence_limitations: list[str], alternative_explanations: list[str], recommended_next_steps: list[str]) -> dict:
        return {
            "agent": "Judge",
            "verdict": verdict,
            "confidence": confidence,
            "best_current_assessment": reason,
            "leading_hypothesis": leading_hypothesis,
            "confidence_level": f"{round(confidence * 100)}%",
            "evidence_supporting": evidence_supporting,
            "evidence_limitations": evidence_limitations,
            "alternative_explanations": alternative_explanations,
            "recommended_next_steps": recommended_next_steps,
            "reason": reason,
            "what_would_change_verdict": recommended_next_steps,
            "supporting_evidence_ids": [],
            "strongest_defense_argument": "No defense challenge was recorded.",
            "uncertainty": "; ".join(evidence_limitations),
        }

    def decide(self, prosecutor: dict, defense: dict, reproduction: dict, *, mode: str = "user") -> dict:
        has_citations = bool(prosecutor.get("citations"))
        before_failed = reproduction.get("before", {}).get("status") == "FAIL"
        before_passed = reproduction.get("before", {}).get("status") == "PASS"
        leading_hypothesis = prosecutor.get("position") or "No clear leading hypothesis identified."
        supporting = prosecutor.get("citations") or ["No direct source cite was available for this investigation."]
        alternatives = defense.get("alternatives") or ["No alternative explanation has been prioritized yet."]
        missing = defense.get("missing_evidence") or [
            "Application logs, stack traces, or runtime data were not available.",
            "A targeted reproduction was not performed in an isolated environment."
        ]

        def verdict(result: dict) -> dict:
            result["supporting_evidence_ids"] = prosecutor.get("evidence_ids", [])
            challenges = defense.get("challenges", [])
            result["strongest_defense_argument"] = challenges[0]["argument"] if challenges else (defense.get("argument") or "No defense challenge was recorded.")
            result["uncertainty"] = "; ".join(result.get("evidence_limitations", []))
            return result

        if reproduction.get("before", {}).get("status") == "PASS" and has_citations:
            return verdict(self._make_verdict(
                verdict="REJECTED",
                confidence=0.82,
                leading_hypothesis="The current hypothesis is contradicted by the available reproduction data.",
                reason="The strongest hypothesis is currently contradicted by the observed execution result; the evidence does not support the root-cause claim.",
                evidence_supporting=[
                    "The available code or log evidence suggested a likely issue, but the reproduction data did not match that outcome.",
                    "The check result explicitly failed to reproduce the expected failure path."
                ],
                evidence_limitations=[
                    "The environment may not match the production or incident conditions.",
                    "Only the available reproduction data was checked; additional runtime context may still be missing."
                ],
                alternative_explanations=alternatives,
                recommended_next_steps=[
                    "Confirm the reproduction setup matches the reported incident conditions.",
                    "Compare the failing code path against environment-specific variables and deployment configuration.",
                    "Look for logs or runtime traces that show a different triggering condition than the current reproduction."
                ],
            ))

        if mode == "demo":
            if before_failed and has_citations:
                return verdict(self._make_verdict(
                    verdict="CONFIRMED",
                    confidence=0.91,
                    leading_hypothesis=leading_hypothesis,
                    reason="The failure was reproduced and the available evidence directly supports the root-cause hypothesis.",
                    evidence_supporting=[f"Direct reproduction result matches the reported failure path: {supporting[0]}"] if supporting else ["Direct reproduction result matches the reported failure path."],
                    evidence_limitations=[
                        "The demo environment is controlled and may not capture all production conditions.",
                        "Independent verification in a wider environment remains valuable."
                    ],
                    alternative_explanations=alternatives,
                    recommended_next_steps=[
                        "Run the same reproduction in an isolated environment to confirm the fix.",
                        "Review adjacent validation and configuration paths for related edge cases."
                    ],
                ))

            if has_citations or before_failed:
                return verdict(self._make_verdict(
                    verdict="MOST_LIKELY",
                    confidence=0.62,
                    leading_hypothesis=leading_hypothesis,
                    reason="The available evidence identifies a leading root-cause hypothesis, but complete proof or independent verification is still unavailable.",
                    evidence_supporting=supporting,
                    evidence_limitations=[
                        "Application logs and runtime reproduction were not fully available.",
                        "The current assessment is limited to static and contextual evidence."
                    ],
                    alternative_explanations=alternatives,
                    recommended_next_steps=[
                        "Add the missing log evidence or failing runtime trace.",
                        "Run the targeted reproduction test in an isolated environment.",
                        "Compare the suspected code path against the alternative explanations listed above."
                    ],
                ))

            return verdict(self._make_verdict(
                verdict="MORE_EVIDENCE_NEEDED",
                confidence=0.34,
                leading_hypothesis="No single cause is strongly supported by the current evidence.",
                reason="The investigation has not identified a dependable root-cause claim from the evidence currently available.",
                evidence_supporting=["No direct evidence tied the issue to a specific failure path."],
                evidence_limitations=[
                    "The supplied data does not include a failing test, runtime trace, or clear error reproduction.",
                    "The investigation remains limited by missing evidence and unresolved alternatives."
                ],
                alternative_explanations=alternatives,
                recommended_next_steps=[
                    "Provide application logs, a stack trace, or a failing test.",
                    "Collect a reproduction or deployment context that matches the incident.",
                    "Re-run the investigation once the missing evidence is available."
                ],
            ))

        if before_failed and has_citations:
            return verdict(self._make_verdict(
                verdict="CONFIRMED",
                confidence=0.78,
                leading_hypothesis=leading_hypothesis,
                reason="The available evidence and reproduction data point to a single root-cause explanation that is consistent with the reported failure.",
                evidence_supporting=supporting,
                evidence_limitations=[
                    "The environment may not fully match the original incident context.",
                    "Independent verification would strengthen the confidence in the conclusion."
                ],
                alternative_explanations=alternatives,
                recommended_next_steps=[
                    "Validate the fix with the same failing input in a controlled environment.",
                    "Confirm there are no other execution paths that trigger the same error." 
                ],
            ))

        if has_citations or before_failed:
            return verdict(self._make_verdict(
                verdict="MOST_LIKELY",
                confidence=0.62,
                leading_hypothesis=leading_hypothesis,
                reason="A clear leading hypothesis exists based on the available evidence, but complete proof or runtime verification is still unavailable.",
                evidence_supporting=supporting,
                evidence_limitations=missing,
                alternative_explanations=alternatives,
                recommended_next_steps=[
                    "Collect logs or stack-trace data tied to the incident.",
                    "Run the targeted reproduction in an isolated environment.",
                    "Validate whether the leading hypothesis remains the best explanation once the missing evidence is gathered."
                ],
            ))

        return verdict(self._make_verdict(
            verdict="MORE_EVIDENCE_NEEDED",
            confidence=0.28,
            leading_hypothesis="No specific root cause is yet supported strongly enough to prioritize.",
            reason="Multiple hypotheses remain plausible and the available evidence is insufficient to responsibly select one as the leading cause.",
            evidence_supporting=["The repository was analyzed, but no direct incident-specific evidence was supplied."],
            evidence_limitations=[
                "No logs, stack trace, failing test, or runtime reproduction were provided.",
                "The system has not yet connected the issue to a concrete execution path."
            ],
            alternative_explanations=alternatives,
            recommended_next_steps=[
                "Gather a realistic error log, stack trace, or failure report.",
                "Identify the exact operation or request that triggered the incident.",
                "Attach a failing test or reproduction input that matches the reported behavior."
            ],
        ))
