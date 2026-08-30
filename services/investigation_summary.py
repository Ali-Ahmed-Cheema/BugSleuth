"""
Investigation Summary and Readiness Analysis Service

Generates:
- Investigation Readiness Score (pre-investigation)
- Investigation Summary (post-investigation)
- Evidence Strength classification
- Recommended Next Actions
- Investigation Activity Timeline
"""

from pathlib import Path


class InvestigationReadiness:
    """Calculate readiness score before investigation starts."""
    
    @staticmethod
    def calculate(package: dict) -> dict:
        """
        Analyze available evidence and return readiness assessment.
        
        Returns dict with:
        - score: 0-100 readiness percentage
        - available: list of available evidence types
        - missing: list of missing evidence types
        - explanation: narrative description
        """
        available = []
        missing = []
        weight_sum = 0
        available_weight = 0
        
        # Source code
        if package.get("source_path"):
            available.append("Source Code")
            weight_sum += 25
            available_weight += 25
        else:
            missing.append("Source Code (ZIP or GitHub repository)")
            weight_sum += 25
        
        # Application logs
        if package.get("logs_path"):
            available.append("Application Logs")
            weight_sum += 30
            available_weight += 30
        else:
            missing.append("Application Logs from incident timeframe")
            weight_sum += 30
        
        # Git history / Change evidence
        if package.get("history_path"):
            available.append("Git History & Changes")
            weight_sum += 20
            available_weight += 20
        else:
            missing.append("Git History (for commit analysis)")
            weight_sum += 20
        
        # Stack trace / error report
        observation = (package.get("user_observation") or "").lower()
        has_stack_trace = any(token in observation for token in ["traceback", "stack trace", "exception", "at line"])
        if has_stack_trace:
            available.append("Stack Trace or Error Report")
            weight_sum += 15
            available_weight += 15
        else:
            missing.append("Stack Trace or detailed error report")
            weight_sum += 15
        
        # Runtime evidence
        has_runtime = any(token in observation for token in ["error", "failed", "timeout", "crash", "500"])
        if has_runtime:
            available.append("Runtime Error or Failure Evidence")
            weight_sum += 10
            available_weight += 10
        else:
            missing.append("Runtime reproduction or failure evidence")
            weight_sum += 10
        
        score = int((available_weight / weight_sum * 100)) if weight_sum > 0 else 0
        
        return {
            "readiness_score": score,
            "available_evidence": available,
            "missing_evidence": missing,
            "readiness_level": _classify_readiness(score),
            "explanation": _readiness_explanation(score, available, missing),
        }
    
    @staticmethod
    def pre_investigation_summary(readiness: dict) -> str:
        """Generate a pre-investigation readiness message."""
        score = readiness["readiness_score"]
        if score >= 75:
            return "BugSleuth has sufficient evidence to begin investigation. All key evidence types are available."
        elif score >= 50:
            return "BugSleuth can begin investigating with the available evidence. Some runtime or incident-specific evidence is missing, which may limit verification certainty."
        else:
            return "BugSleuth can investigate with the available repository evidence. Additional runtime logs, stack traces, or reproduction steps would significantly improve accuracy and verifiability."


class EvidenceStrength:
    """Classify the strength of collected evidence."""
    
    @staticmethod
    def calculate(investigators: list) -> dict:
        """
        Analyze all investigators to determine overall evidence strength.
        
        Returns:
        - strength_level: VERY_STRONG, STRONG, MODERATE, LIMITED, INSUFFICIENT
        - percentage: 0-100 score
        - sources_count: number of evidence sources analyzed
        - breakdown: detail of each source's contribution
        """
        sources = []
        strength_score = 0
        max_score = 0
        
        for investigator in investigators:
            agent = investigator.get("agent", "Unknown")
            status = investigator.get("status", "unavailable")
            confidence = investigator.get("confidence", 0.0)
            findings = investigator.get("findings", [])
            
            if status == "complete":
                findings_count = len(findings)
                score = min(25, findings_count * 3) * confidence
                strength_score += score
                max_score += 25
                
                sources.append({
                    "agent": agent,
                    "status": "Available",
                    "findings": findings_count,
                    "confidence": f"{int(confidence * 100)}%",
                })
            else:
                sources.append({
                    "agent": agent,
                    "status": "Unavailable",
                    "findings": 0,
                    "confidence": "0%",
                })
                max_score += 25
        
        percentage = int((strength_score / max_score * 100)) if max_score > 0 else 0
        strength_level = _classify_strength(percentage)
        
        return {
            "strength_level": strength_level,
            "percentage": percentage,
            "sources_analyzed": len([s for s in sources if s["status"] == "Available"]),
            "total_sources": len(sources),
            "sources": sources,
        }


class InvestigationSummary:
    """Generate executive investigation summary."""
    
    @staticmethod
    def generate(verdict: dict, evidence_strength: dict, hypotheses: list, ledger: dict, 
                 demo: bool = False) -> dict:
        """
        Create executive summary of investigation results.
        """
        # Determine hypothesis confidence level
        hypothesis_confidence = verdict.get("confidence", 0.0)
        leading_hypothesis = verdict.get("leading_hypothesis", "Unknown")
        
        # Determine verification status
        verification_status = _determine_verification_status(verdict, ledger, demo)
        
        # Summary findings
        what_we_know = []
        what_we_know.extend([f"✓ {src['agent']}" for src in evidence_strength.get("sources", []) if src["status"] == "Available"])
        
        what_we_need = []
        what_we_need.extend([f"⚠ {item}" for item in ledger.get("missing_evidence", [])[:3]])
        
        # Recommended immediate next step
        recommended_step = _get_primary_recommendation(ledger.get("what_would_change_verdict", []))
        
        return {
            "verdict": verdict.get("verdict", "UNKNOWN"),
            "verdict_explanation": verdict.get("reason", "No explanation available"),
            "evidence_strength": evidence_strength["strength_level"],
            "hypothesis_confidence": f"{int(hypothesis_confidence * 100)}%",
            "verification_status": verification_status,
            "sources_analyzed": f"{evidence_strength['sources_analyzed']} of {evidence_strength['total_sources']}",
            "what_we_know": what_we_know,
            "what_we_need": what_we_need,
            "primary_finding": leading_hypothesis,
            "recommended_next_step": recommended_step,
        }


class RecommendedActions:
    """Generate recommended next actions based on missing evidence and findings."""
    
    @staticmethod
    def generate(ledger: dict, evidence_strength: dict, verdict: dict) -> dict:
        """
        Create categorized recommendations for next investigative steps.
        """
        high_priority = []
        medium_priority = []
        optional = []
        
        missing = ledger.get("missing_evidence", [])
        
        # High priority: Critical evidence that would change verdict
        if "Application logs" in str(missing).lower() or "logs" in str(missing).lower():
            high_priority.append({
                "action": "Provide application logs from the incident timeframe",
                "why": "Logs could connect the suspected code path to the actual runtime failure and significantly strengthen or disprove the current hypothesis.",
                "priority": "HIGH",
            })
        
        if "Stack trace" in str(missing).lower() or "traceback" in str(missing).lower():
            high_priority.append({
                "action": "Provide the stack trace or exception report",
                "why": "A stack trace would pinpoint the exact execution path and immediately confirm or eliminate the suspected root cause.",
                "priority": "HIGH",
            })
        
        if "failing test" in str(missing).lower() or "test" in str(missing).lower():
            high_priority.append({
                "action": "Identify or run the failing test that reproduces the incident",
                "why": "A reproducible test case would provide definitive proof of the root cause and enable verification of any fix.",
                "priority": "HIGH",
            })
        
        # Medium priority: Contextual evidence that would improve understanding
        if "git" in str(missing).lower() or "deployment" in str(missing).lower():
            medium_priority.append({
                "action": "Review recent commits related to the affected component",
                "why": "Recent changes are often the cause of new issues. Comparing the suspected code path against recent modifications could identify the triggering change.",
                "priority": "MEDIUM",
            })
        
        if "CI/CD" in str(missing).lower() or "pipeline" in str(missing).lower():
            medium_priority.append({
                "action": "Review deployment configuration or CI/CD pipeline results",
                "why": "Deployment issues or configuration mismatches could be the root cause. Pipeline logs would show whether a deployment-related change triggered the incident.",
                "priority": "MEDIUM",
            })
        
        # Optional: Supplementary evidence
        optional.append({
            "action": "Provide infrastructure or environment configuration details",
            "why": "Environment-specific configurations (database, cache, external services) might reveal the root cause if the suspected code path behaves differently under production conditions.",
            "priority": "OPTIONAL",
        })
        
        return {
            "high_priority": high_priority or [
                {
                    "action": "Confirm the reproduction setup matches the incident conditions",
                    "why": "Ensuring the test environment accurately reflects production behavior is essential for verification.",
                    "priority": "HIGH",
                }
            ],
            "medium_priority": medium_priority or [
                {
                    "action": "Review the proposed hypothesis against the code path",
                    "why": "Manual code review can identify edge cases or assumptions that may not be evident from static analysis.",
                    "priority": "MEDIUM",
                }
            ],
            "optional": optional,
        }


class InvestigationActivityTimeline:
    """Generate investigator activity and status timeline."""
    
    @staticmethod
    def generate(investigators: list) -> list:
        """
        Create a timeline showing each investigator's status and findings.
        """
        timeline = [
            {
                "agent": "Project Intelligence",
                "status": "COMPLETE",
                "icon": "🔍",
                "findings_count": None,
            }
        ]
        
        agent_names = {
            "Log Investigator": "Log Analyzer",
            "Code Investigator": "Code Review",
            "Change Investigator": "Change History",
            "Pipeline Investigator": "CI/CD Pipeline",
            "Deployment Context Investigator": "Deployment Config",
        }
        
        for investigator in investigators:
            agent = investigator.get("agent", "Unknown")
            status = investigator.get("status", "unavailable").upper()
            
            if status == "COMPLETE":
                icon = "✓"
                status_text = "COMPLETE"
                findings_count = len(investigator.get("findings", []))
            elif status == "UNAVAILABLE":
                icon = "✗"
                status_text = "UNAVAILABLE"
                findings_count = 0
            else:
                icon = "●"
                status_text = status
                findings_count = None
            
            display_name = agent_names.get(agent, agent)
            
            timeline.append({
                "agent": display_name,
                "status": status_text,
                "icon": icon,
                "findings_count": findings_count,
                "full_agent_name": agent,
            })
        
        timeline.append({
            "agent": "Tribunal Review",
            "status": "COMPLETE",
            "icon": "⚖",
            "findings_count": None,
        })
        
        return timeline


# Helper functions

def _classify_readiness(score: int) -> str:
    if score >= 75:
        return "HIGH"
    elif score >= 50:
        return "MODERATE"
    else:
        return "LIMITED"


def _readiness_explanation(score: int, available: list, missing: list) -> str:
    base = f"Investigation readiness: {score}%.\n"
    
    if available:
        base += f"Available: {', '.join(available)}.\n"
    if missing:
        base += f"Missing: {', '.join(missing)}.\n"
    
    if score >= 75:
        return base + "BugSleuth has sufficient evidence to conduct a thorough investigation."
    elif score >= 50:
        return base + "BugSleuth can investigate with available evidence. Some runtime or incident-specific evidence is missing, which may limit verification certainty."
    else:
        return base + "BugSleuth can investigate with repository and historical evidence. Additional runtime logs, stack traces, or reproduction steps would significantly improve accuracy."


def _classify_strength(percentage: int) -> str:
    if percentage >= 90:
        return "VERY STRONG"
    elif percentage >= 75:
        return "STRONG"
    elif percentage >= 50:
        return "MODERATE"
    elif percentage >= 25:
        return "LIMITED"
    else:
        return "INSUFFICIENT"


def _determine_verification_status(verdict: dict, ledger: dict, demo: bool) -> str:
    if demo:
        if verdict.get("verdict") == "CONFIRMED":
            return "VERIFIED"
        elif verdict.get("verdict") == "MOST_LIKELY":
            return "PARTIALLY_VERIFIED"
        else:
            return "NOT_VERIFIED"
    else:
        # User investigations cannot auto-verify without running untrusted code
        if "Execution is not enabled" in str(verdict.get("reason", "")):
            return "UNAVAILABLE"
        return "NOT_VERIFIED"


def _get_primary_recommendation(changes_verdict: list) -> str:
    if not changes_verdict:
        return "Complete a controlled reproduction or provide additional runtime evidence."
    
    first = changes_verdict[0]
    if isinstance(first, dict):
        return first.get("action", str(first))
    return str(first)
