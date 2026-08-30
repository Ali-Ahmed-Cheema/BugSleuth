from __future__ import annotations

from pathlib import Path

from investigators import LogInvestigator, CodeInvestigator, ChangeInvestigator, PipelineInvestigator, DeploymentContextInvestigator
from tribunal import Prosecutor, Defense, Judge
from verification import reproduce, generate_fix, verify_fix
from sample_app.payment_service import process_payment, process_payment_fixed
from services.project_analyzer import ProjectAnalyzer
from services.timeline_builder import TimelineBuilder
from services.pattern_detector import PatternDetector
from services.investigation_summary import (
    InvestigationReadiness,
    EvidenceStrength,
    InvestigationSummary,
    RecommendedActions,
    InvestigationActivityTimeline,
)
from services.evidence_catalog import build_evidence_catalog
from services.trust_schema import validate_trust_layer


def _missing(label: str) -> dict:
    messages = {
        "Log Investigator": "No application logs were provided. Log-based evidence is unavailable.",
        "Code Investigator": "No source code was provided. Code-based investigation is unavailable.",
        "Change Investigator": "No deployment or Git history was available for this investigation.",
    }
    return {
        "agent": label,
        "status": "unavailable",
        "findings": [messages[label]],
        "evidence": [],
        "confidence": 0.0,
    }


def _project_discovery(package: dict) -> dict:
    """Discover project profile using the new ProjectAnalyzer."""
    source_path = Path(package.get("source_path")) if package.get("source_path") else None
    github_repo = package.get("github_repository")
    
    profile = ProjectAnalyzer.analyze(source_path, github_repo)
    
    return {
        "project_name": profile.project_name,
        "language": profile.primary_language,
        "framework": profile.framework,
        "test_framework": profile.test_framework,
        "source_file_count": profile.source_file_count,
        "test_file_count": profile.test_file_count,
        "entry_points": profile.entry_points,
        "dependency_files": profile.dependency_files,
        "has_git_history": profile.has_git_history,
        "has_readme": profile.has_readme,
        "detection_confidence": round(profile.detection_confidence, 2),
        # Keep legacy fields for backward compatibility
        "repository": github_repo.get("repository") if github_repo else (package.get("source_filename") or "User-supplied project"),
        "framework_detected": f"Possible framework detected: {profile.framework}" if profile.framework else "Framework detection not yet confident.",
        "git_history": profile.has_git_history,
    }


def _evidence_status(package: dict) -> dict:
    return {
        "application_logs": "Available" if package.get("logs_path") else "Not Provided",
        "error_reports": "Available" if package.get("user_observation") else "Not Provided",
        "stack_trace": "Available" if package.get("user_observation") and any(token in (package.get("user_observation") or "").lower() for token in ["traceback", "error", "exception", "stack trace"]) else "Not Provided",
        "failing_tests": "Detected" if package.get("source_path") and Path(package.get("source_path")).exists() and any("test" in str(path).lower() for path in Path(package.get("source_path")).rglob("*") if path.is_file()) else "Not Detected",
        "git_history": "Available" if package.get("history_path") else "Not Available",
        "ci_cd_results": "Not Connected",
        "source_code": "Available" if package.get("source_path") else "Not Available",
    }


def _has_meaningful_incident_evidence(package: dict) -> bool:
    if package.get("logs_path"):
        return True
    observation = (package.get("user_observation") or "").strip().lower()
    if any(token in observation for token in ["error", "exception", "failed", "traceback", "timeout", "500", "crash", "bug"]):
        return True
    if package.get("source_path") and Path(package.get("source_path")).exists():
        repo_root = Path(package["source_path"])
        if repo_root.is_dir():
            test_files = [path for path in repo_root.rglob("*") if path.is_file() and ("test" in path.name.lower() or "spec" in path.name.lower())]
            if test_files:
                return True
    return False


def run_investigation(package: dict, *, demo: bool = False) -> dict:
    mode = "demo" if demo else "user"
    evidence = []
    if package.get("logs_path"):
        evidence.append(LogInvestigator(Path(package["logs_path"])).investigate(package))
    else:
        evidence.append(_missing("Log Investigator"))
    if package.get("source_path"):
        evidence.append(CodeInvestigator(Path(package["source_path"])).investigate(package))
    else:
        evidence.append(_missing("Code Investigator"))
    if package.get("history_path"):
        evidence.append(ChangeInvestigator(Path(package["history_path"])).investigate(package))
    else:
        evidence.append(_missing("Change Investigator"))

    source_root = Path(package["source_path"]) if package.get("source_path") else None
    if source_root and source_root.exists():
        evidence.append(PipelineInvestigator(source_root).investigate(package))
        evidence.append(DeploymentContextInvestigator(source_root).investigate(package))
    else:
        evidence.append({
            "agent": "Pipeline Investigator",
            "status": "complete",
            "pipeline_detected": False,
            "findings": ["No supported CI/CD configuration was detected in the supplied project."],
            "evidence": [],
            "confidence": 0.0,
            "workflow_files": [],
            "trigger_events": [],
            "test_steps": [],
            "deployment_steps": [],
            "execution_result_available": False,
        })
        evidence.append({
            "agent": "Deployment Context Investigator",
            "status": "complete",
            "findings": ["No supported deployment or container configuration was detected."],
            "evidence": [],
            "confidence": 0.0,
            "deployment_profile": {
                "containerization": "Not detected",
                "orchestration": "Not detected",
                "infrastructure_as_code": "Not detected",
                "cloud_provider": "Not confidently identified",
            },
        })

    project_discovery = _project_discovery(package) if not demo else {
        "project_name": "payment-service",
        "language": "Python",
        "framework": "Flask",
        "test_framework": "Pytest",
        "source_file_count": 24,
        "test_file_count": 8,
        "entry_points": ["app.py"],
        "dependency_files": ["requirements.txt"],
        "has_git_history": True,
        "has_readme": True,
        "detection_confidence": 0.95,
        # Legacy fields
        "repository": "demo/payment-service",
        "framework_detected": "Possible framework detected: Flask",
        "git_history": True,
    }
    
    evidence_status = _evidence_status(package) if not demo else {
        "application_logs": "Available",
        "error_reports": "Available",
        "stack_trace": "Available",
        "failing_tests": "Detected",
        "git_history": "Available",
        "ci_cd_results": "Not Connected",
        "source_code": "Available",
    }

    # Build timeline from available evidence
    logs_path = Path(package["logs_path"]) if package.get("logs_path") else None
    history_path = Path(package["history_path"]) if package.get("history_path") else None
    timeline = TimelineBuilder.build_timeline(package["investigation_id"], logs_path, history_path)
    TimelineBuilder.add_incident_event(timeline)
    TimelineBuilder.add_investigation_start(timeline)

    hypotheses = ["The available evidence points to a defect in the application code."]
    hypotheses.extend(["Database latency caused the failure.", "A deployment configuration issue caused the failure."])
    if demo:
        hypotheses[0] = package["incident"]["hypotheses"][0]
    else:
        hypotheses = [
            "The repository was analyzed, but no active incident evidence was supplied.",
            "The issue may be caused by a runtime failure, configuration issue, or code path that is not yet evidenced.",
            "A deployment or environment change may explain the observed behavior if additional evidence appears."
        ]

    reproduction = {"before": reproduce(process_payment), "after": verify_fix(process_payment_fixed)} if demo else {
        "before": {"status": "UNAVAILABLE", "message": "Execution is not enabled for untrusted user repositories in this prototype."},
        "after": {"status": "UNAVAILABLE", "message": "Execution is not enabled for untrusted user repositories in this prototype."},
    }

    facts = build_evidence_catalog(evidence)
    prosecutor = Prosecutor().analyze(evidence, hypotheses[0], facts=facts, mode=mode)
    defense = Defense().analyze(evidence, hypotheses, facts=facts, mode=mode)
    judge = Judge().decide(prosecutor, defense, reproduction, mode=mode)

    if not demo and not _has_meaningful_incident_evidence(package):
        judge["verdict"] = "MORE_EVIDENCE_NEEDED"
        judge["confidence"] = 0.24
        judge["best_current_assessment"] = "The repository was analyzed, but no direct incident-specific evidence was supplied. The leading cause cannot be selected responsibly from the current information."
        judge["leading_hypothesis"] = "No specific root cause is yet supported strongly enough to prioritize."
        judge["evidence_limitations"] = [
            "No logs, stack trace, failing test, or runtime reproduction were provided.",
            "The investigation remains limited to repository structure and static evidence."
        ]
        judge["alternative_explanations"] = [
            "A runtime configuration issue may be causing the observed behavior.",
            "A deployment change or environment difference could be responsible."
        ]
        judge["recommended_next_steps"] = [
            "Provide the exact log line, stack trace, or error report that matches the incident.",
            "Run the relevant request or test in an isolated environment to capture the failing path.",
            "Compare the suspected code path with deployment and configuration differences."
        ]
        judge["reason"] = "Multiple hypotheses remain plausible and the available evidence is insufficient to responsibly select one as the leading cause."
        judge["what_would_change_verdict"] = judge["recommended_next_steps"]

    hypothesis = {
        "id": "H-001",
        "statement": judge["leading_hypothesis"],
        "verdict": judge["verdict"],
        "confidence": judge["confidence"],
        "evidence_ids": prosecutor.get("evidence_ids", []),
        "causal_chain": prosecutor.get("causal_chain", []),
        "attribution": "REASONING",
    }
    verification = {
        "status": "available" if demo else "unavailable",
        "execution_policy": "trusted_demo_only" if demo else "untrusted_code_not_executed",
        "message": "Run RED → GREEN verification against a temporary demo copy." if demo else "Verification is intentionally unavailable for uploaded or GitHub code. Review the supplied reproduction plan in a controlled environment.",
    }
    trust_layer = {
        "facts": facts,
        "hypothesis": hypothesis,
        "tribunal": {"prosecutor": prosecutor, "defense": defense, "judge": judge},
        "verification": verification,
    }
    trust_layer["validation_errors"] = validate_trust_layer(trust_layer)

    # Detect similar patterns if root cause likely involves validation logic
    similar_patterns_list = []
    if not demo and package.get("source_path"):
        source_path = Path(package["source_path"])
        similar_patterns_list = PatternDetector.find_all_patterns(source_path, max_results=10)

    available_evidence = [finding for item in evidence for finding in item["findings"] if item["status"] == "complete"]
    missing = [finding for item in evidence for finding in item["findings"] if item["status"] == "unavailable"]
    ledger = {
        "verdict": judge["verdict"],
        "confidence": judge["confidence"],
        "facts": [item for item in available_evidence if item],
        "observations": ["Repository and project metadata were discovered successfully.", "The investigation remains limited to the evidence supplied by the user."],
        "hypotheses": [hypothesis for hypothesis in hypotheses[:1] if hypothesis],
        "missing_evidence": missing + (["No active incident evidence was identified in the supplied repository or logs."] if not demo and not _has_meaningful_incident_evidence(package) else []),
        "evidence_for": available_evidence,
        "evidence_against": ["No direct runtime reproduction or production evidence was collected for this investigation."] if not demo else ["The investigation has no direct production replay or metrics export."],
        "alternatives": [{"name": alternative, "status": "UNRESOLVED" if not demo else "REJECTED", "reason": "No direct supporting evidence was supplied."} for alternative in hypotheses[1:]],
        "what_would_change_verdict": judge["what_would_change_verdict"],
        "human_verification": ["Review every cited source line.", "Run tests in a controlled environment.", "Approve deployment separately."],
    }
    
    # Generate new v6 transparency features
    evidence_strength_data = EvidenceStrength.calculate(evidence)
    investigation_summary_data = InvestigationSummary.generate(
        judge, evidence_strength_data, hypotheses, ledger, demo=demo
    )
    recommended_actions_data = RecommendedActions.generate(ledger, evidence_strength_data, judge)
    investigator_timeline_data = InvestigationActivityTimeline.generate(evidence)
    
    return {
        "incident": package["incident"],
        "investigation_id": package["investigation_id"],
        "demo": demo,
        "mode": mode,
        "trust_layer": trust_layer,
        # NEW IN v6: Investigation Summary and Trust Metrics
        "investigation_summary": investigation_summary_data,
        "evidence_strength": evidence_strength_data,
        "recommended_actions": recommended_actions_data,
        "investigator_timeline": investigator_timeline_data,
        # EXISTING FIELDS
        "project_discovery": project_discovery,
        "evidence_status": evidence_status,
        "timeline": timeline.to_dict(),
        "investigators": evidence,
        "hypotheses": hypotheses,
        "tribunal": {"prosecutor": prosecutor, "defense": defense, "judge": judge},
        "ledger": ledger,
        "similar_patterns": [pattern.to_dict() for pattern in similar_patterns_list],
        "proof": {
            "reproduction": reproduction["before"],
            "fix": generate_fix() if demo else {"description": "Execution is not enabled for this repository.", "diff": "No executable fix was generated for untrusted repository code."},
            "verification": reproduction["after"],
        },
    }
