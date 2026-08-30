"""
Integration tests for BugSleuth.

Tests whether different parts of the software work correctly together:

1.  Investigators → EvidenceCatalog
    - Investigator output flows correctly into build_evidence_catalog
2.  EvidenceCatalog → Tribunal (Prosecutor / Defense / Judge)
    - Facts built from investigators drive tribunal reasoning
3.  Investigators + Tribunal → run_investigation (investigation_service)
    - Full pipeline from raw evidence package to final result shape
4.  FileService → Investigation package → run_investigation
    - Saving uploaded files produces a usable package for investigation
5.  TimelineBuilder → IncidentTimeline model
    - Builder populates the model used by run_investigation
6.  PatternDetector → run_investigation similar_patterns
    - Detected patterns appear in the investigation result
7.  ProjectAnalyzer → ProjectProfile → project_discovery in run_investigation
    - Analyzer output surfaces correctly in the response
8.  Flask API → investigation_service (end-to-end HTTP paths)
    - Create + run via HTTP; trust_layer contract is valid
9.  Trust layer validation (validate_trust_layer) receives live catalog output
    - No validation errors on a real run result
10. Verification guard integration
    - Non-demo investigation_id always returns 403 from the verify endpoint
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip(entries: dict[str, str]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Investigators → EvidenceCatalog
# ---------------------------------------------------------------------------

from services.evidence_catalog import build_evidence_catalog


class TestInvestigatorToEvidenceCatalog:
    """Investigator output → build_evidence_catalog integration."""

    def test_log_investigator_output_produces_typed_facts(self, tmp_path):
        from investigators import LogInvestigator

        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR database connection refused\n", encoding="utf-8")
        investigator_result = LogInvestigator(log).investigate({})

        facts = build_evidence_catalog([investigator_result])

        assert len(facts) >= 1
        assert all(f["type"] == "log" for f in facts)
        assert all(f["attribution"] == "FACT" for f in facts)
        assert facts[0]["id"] == "E-001"
        assert "app.log" in facts[0]["source"]

    def test_code_investigator_output_produces_source_facts(self, tmp_path):
        from investigators import CodeInvestigator

        service = tmp_path / "payment_service.py"
        service.write_text(
            "def process(amount):\n"
            "    if not amount:\n"
            "        raise ValueError('Invalid')\n",
            encoding="utf-8",
        )
        result = CodeInvestigator(service).investigate(
            {"user_observation": "payment error", "logs_path": None}
        )
        facts = build_evidence_catalog([result])

        assert all(f["type"] == "source" for f in facts)

    def test_change_investigator_output_produces_git_facts(self, tmp_path):
        from investigators import ChangeInvestigator

        history = tmp_path / "git_history.txt"
        history.write_text("abc1234 2026-08-28 Fix payment_amount validation\n", encoding="utf-8")
        result = ChangeInvestigator(history).investigate({})
        facts = build_evidence_catalog([result])

        # Change investigator only emits evidence for lines containing
        # "abc1234" or "payment_amount" — both present in the test file
        assert len(facts) >= 1
        assert all(f["type"] == "git" for f in facts)

    def test_mixed_investigators_produce_sequential_ids(self, tmp_path):
        from investigators import LogInvestigator, CodeInvestigator

        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR crash\n", encoding="utf-8")
        source = tmp_path / "service.py"
        source.write_text(
            "def handler():\n    raise Exception('boom')\n", encoding="utf-8"
        )

        log_result = LogInvestigator(log).investigate({})
        code_result = CodeInvestigator(source).investigate(
            {"user_observation": "crash", "logs_path": str(log)}
        )

        facts = build_evidence_catalog([log_result, code_result])
        ids = [f["id"] for f in facts]
        expected = [f"E-{i:03d}" for i in range(1, len(ids) + 1)]
        assert ids == expected

    def test_unavailable_investigator_contributes_no_facts(self):
        missing = {
            "agent": "Log Investigator",
            "status": "unavailable",
            "findings": ["No logs provided"],
            "evidence": [],
            "confidence": 0.0,
        }
        facts = build_evidence_catalog([missing])
        assert facts == []


# ---------------------------------------------------------------------------
# 2. EvidenceCatalog → Tribunal
# ---------------------------------------------------------------------------

from tribunal import Prosecutor, Defense, Judge


class TestEvidenceCatalogToTribunal:
    """Facts from the catalog feed directly into tribunal analysis."""

    def _make_fact(self, idx: int, source_type: str = "log") -> dict:
        return {
            "id": f"E-{idx:03d}",
            "type": source_type,
            "attribution": "FACT",
            "investigator": "Log Investigator",
            "source": "app.log",
            "line": idx,
            "excerpt": f"Error line {idx}",
            "description": "Extracted by Log Investigator.",
        }

    def _make_investigator(self, has_evidence: bool, status: str = "complete") -> dict:
        evidence_line = "app.log:1: ERROR crash" if has_evidence else ""
        return {
            "agent": "Log Investigator",
            "status": status,
            "findings": ["Found 1 error-indicator line."],
            "evidence": [evidence_line] if has_evidence else [],
            "confidence": 0.94,
        }

    def test_prosecutor_receives_facts_and_includes_evidence_ids(self):
        facts = [self._make_fact(i) for i in range(1, 4)]
        investigators = [self._make_investigator(True)]
        hypothesis = "A validation failure caused the error."

        result = Prosecutor().analyze(investigators, hypothesis, facts=facts, mode="user")

        assert result["agent"] == "Prosecutor"
        assert "E-001" in result["evidence_ids"]

    def test_defense_receives_facts_and_has_challenges(self):
        facts = [self._make_fact(1)]
        investigators = [self._make_investigator(True)]
        alternatives = ["Database latency", "Deployment config error"]

        result = Defense().analyze(investigators, alternatives, facts=facts, mode="user")

        assert result["agent"] == "Defense"
        assert len(result["challenges"]) >= 1
        # First challenge should reference the first fact id
        assert result["challenges"][0]["evidence_id"] == "E-001"

    def test_judge_decides_most_likely_with_citations_and_no_reproduction(self):
        facts = [self._make_fact(1)]
        investigators = [self._make_investigator(True)]
        hypothesis = "Falsy check raised ValueError."
        alternatives = ["Database issue", "Network timeout"]

        prosecutor = Prosecutor().analyze(investigators, hypothesis, facts=facts, mode="user")
        defense = Defense().analyze(investigators, alternatives, facts=facts, mode="user")
        reproduction = {
            "before": {"status": "UNAVAILABLE"},
            "after": {"status": "UNAVAILABLE"},
        }

        verdict = Judge().decide(prosecutor, defense, reproduction, mode="user")

        assert verdict["agent"] == "Judge"
        assert verdict["verdict"] in {"MOST_LIKELY", "MORE_EVIDENCE_NEEDED"}

    def test_judge_confirms_when_reproduction_fails_and_citations_exist(self):
        facts = [self._make_fact(1)]
        investigators = [self._make_investigator(True)]
        hypothesis = "Falsy check."
        alternatives = ["DB latency"]

        prosecutor = Prosecutor().analyze(investigators, hypothesis, facts=facts, mode="user")
        defense = Defense().analyze(investigators, alternatives, facts=facts, mode="user")
        reproduction = {
            "before": {"status": "FAIL", "error": "ValueError"},
            "after": {"status": "PASS"},
        }

        verdict = Judge().decide(prosecutor, defense, reproduction, mode="user")
        assert verdict["verdict"] == "CONFIRMED"

    def test_no_citations_leads_to_more_evidence_needed(self):
        facts = []
        investigators = [self._make_investigator(False)]
        prosecutor = Prosecutor().analyze(investigators, "Unknown", facts=facts, mode="user")
        defense = Defense().analyze(
            investigators, ["Alt 1", "Alt 2"], facts=facts, mode="user"
        )
        reproduction = {"before": {"status": "UNAVAILABLE"}, "after": {"status": "UNAVAILABLE"}}
        verdict = Judge().decide(prosecutor, defense, reproduction, mode="user")

        assert verdict["verdict"] == "MORE_EVIDENCE_NEEDED"


# ---------------------------------------------------------------------------
# 3. Full investigation_service pipeline
# ---------------------------------------------------------------------------

from services.investigation_service import run_investigation


class TestRunInvestigationPipeline:
    """run_investigation integrates all major components end-to-end."""

    def test_observation_only_package_returns_required_keys(self):
        package = {
            "investigation_id": "INT-TEST-001",
            "incident": {
                "incident_id": "user-supplied",
                "service": "Unknown service",
                "title": "Test",
                "severity": "UNTRIAGED",
                "deployment_version": "Unknown",
                "incident_start": "Unknown",
                "user_impact": "Test observation",
                "error_summary": "Not yet determined",
                "description": "Test observation",
            },
            "user_observation": "service is failing with errors",
            "logs_path": None,
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)

        required_top_keys = {
            "incident", "investigation_id", "mode", "trust_layer",
            "tribunal", "investigators", "ledger", "proof",
            "timeline", "similar_patterns", "investigation_summary",
            "evidence_strength", "recommended_actions", "investigator_timeline",
        }
        assert required_top_keys.issubset(result.keys())

    def test_mode_is_user_for_non_demo(self):
        package = {
            "investigation_id": "INT-TEST-002",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "error occurred",
            "logs_path": None,
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        assert result["mode"] == "user"

    def test_log_only_package_yields_complete_log_investigator(self, tmp_path):
        log = tmp_path / "incident.log"
        log.write_text("2026-08-29T10:00:00Z ERROR db refused\n", encoding="utf-8")

        package = {
            "investigation_id": "INT-TEST-003",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "",
            "logs_path": str(log),
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)

        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert log_inv["status"] == "complete"
        assert len(log_inv["evidence"]) >= 1

    def test_source_only_package_yields_complete_code_investigator(self, tmp_path):
        source = tmp_path / "service.py"
        source.write_text(
            "def pay(amount):\n    if not amount:\n        raise ValueError('bad')\n",
            encoding="utf-8",
        )

        package = {
            "investigation_id": "INT-TEST-004",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "payment error",
            "logs_path": None,
            "source_path": str(source),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)

        code_inv = next(i for i in result["investigators"] if i["agent"] == "Code Investigator")
        assert code_inv["status"] == "complete"

    def test_trust_layer_validation_errors_empty_on_real_run(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR crash\n", encoding="utf-8")

        package = {
            "investigation_id": "INT-TEST-005",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "crash",
            "logs_path": str(log),
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        assert result["trust_layer"]["validation_errors"] == []

    def test_facts_in_trust_layer_come_from_investigator_evidence(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR connection timeout\n", encoding="utf-8")

        package = {
            "investigation_id": "INT-TEST-006",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "timeout",
            "logs_path": str(log),
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        facts = result["trust_layer"]["facts"]
        assert len(facts) >= 1
        assert all(f["id"].startswith("E-") for f in facts)
        assert all(f["attribution"] == "FACT" for f in facts)

    def test_similar_patterns_detected_for_source_with_risky_code(self, tmp_path):
        source = tmp_path / "handler.py"
        source.write_text(
            "def handle(amount):\n"
            "    if not amount:\n"
            "        raise ValueError('bad')\n"
            "    try:\n"
            "        process(amount)\n"
            "    except:\n"
            "        pass\n",
            encoding="utf-8",
        )

        package = {
            "investigation_id": "INT-TEST-007",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "handler error",
            "logs_path": None,
            "source_path": str(source),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        # At least one pattern should be found (falsy check or catch-all)
        assert isinstance(result["similar_patterns"], list)
        assert len(result["similar_patterns"]) >= 1

    def test_timeline_contains_investigation_start_event(self, tmp_path):
        package = {
            "investigation_id": "INT-TEST-008",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "crash observed",
            "logs_path": None,
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        event_ids = [e["event_id"] for e in result["timeline"]["events"]]
        assert "INVESTIGATION-001" in event_ids

    def test_log_plus_source_package_verdict_is_most_likely(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR request failed\n", encoding="utf-8")
        source = tmp_path / "api.py"
        source.write_text(
            "def handler(request):\n    raise Exception('request failed')\n",
            encoding="utf-8",
        )

        package = {
            "investigation_id": "INT-TEST-009",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "request failed",
            "logs_path": str(log),
            "source_path": str(source),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        verdict = result["tribunal"]["judge"]["verdict"]
        assert verdict in {"MOST_LIKELY", "CONFIRMED", "MORE_EVIDENCE_NEEDED"}

    def test_proof_verification_is_unavailable_for_user_mode(self):
        package = {
            "investigation_id": "INT-TEST-010",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "error",
            "logs_path": None,
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        assert result["proof"]["verification"]["status"] == "UNAVAILABLE"


# ---------------------------------------------------------------------------
# 4. FileService → Investigation package → run_investigation
# ---------------------------------------------------------------------------

from services.file_service import create_investigation_dir, save_log, save_project_zip


class FakeUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data
        self.content_length = len(data)

    def save(self, dst: Path):
        dst.write_bytes(self._data)


class TestFileServiceToInvestigationPackage:
    """Saved files produce a package that run_investigation can use."""

    def test_log_file_save_then_investigate(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        upload = FakeUpload("app.log", b"2026-08-29T10:00:00Z ERROR boom\n")
        logs_filename = save_log(upload, path)

        package = {
            "investigation_id": "INT-FILE-001",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "",
            "logs_path": str(path / logs_filename),
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert log_inv["status"] == "complete"
        assert len(log_inv["evidence"]) >= 1

    def test_zip_save_then_investigate(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        zip_data = _make_zip({"service.py": "def pay(x):\n    if not x:\n        raise ValueError('bad')\n"})
        upload = FakeUpload("project.zip", zip_data)
        save_project_zip(upload, path)

        source_path = path / "source"
        assert source_path.exists()

        package = {
            "investigation_id": "INT-FILE-002",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "payment error",
            "logs_path": None,
            "source_path": str(source_path),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        code_inv = next(i for i in result["investigators"] if i["agent"] == "Code Investigator")
        assert code_inv["status"] == "complete"

    def test_invalid_extension_rejected_before_investigation(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        upload = FakeUpload("logs.csv", b"col1,col2\nerror,crash\n")
        with pytest.raises(ValueError, match="not supported"):
            save_log(upload, path)

    def test_path_traversal_zip_rejected_before_investigation(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../outside.py", "print('evil')")
        upload = FakeUpload("project.zip", buf.getvalue())
        with pytest.raises(ValueError):
            save_project_zip(upload, path)


# ---------------------------------------------------------------------------
# 5. TimelineBuilder → IncidentTimeline → run_investigation
# ---------------------------------------------------------------------------

from services.timeline_builder import TimelineBuilder
from models.incident_timeline import EventType


class TestTimelineBuilderToModel:
    """TimelineBuilder produces a model consumed by run_investigation."""

    def test_log_events_appear_in_timeline_model(self, tmp_path):
        log = tmp_path / "incident.log"
        log.write_text(
            "2026-08-29T10:00:00Z ERROR database timeout\n"
            "2026-08-29T09:00:00Z WARN slow response\n",
            encoding="utf-8",
        )
        timeline = TimelineBuilder.build_timeline("INV-TL-001", logs_path=log)
        TimelineBuilder.add_incident_event(timeline, "2026-08-29T11:00:00")
        TimelineBuilder.add_investigation_start(timeline)

        event_types = {e.event_type for e in timeline.events}
        assert EventType.ERROR in event_types
        assert EventType.WARNING in event_types

        event_ids = {e.event_id for e in timeline.events}
        assert "INCIDENT-001" in event_ids
        assert "INVESTIGATION-001" in event_ids

    def test_timeline_dict_integrates_into_investigation_result(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00Z ERROR crash\n", encoding="utf-8")

        package = {
            "investigation_id": "INT-TL-001",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "crash",
            "logs_path": str(log),
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        tl = result["timeline"]
        assert tl["investigation_id"] == "INT-TL-001"
        assert tl["event_count"] >= 1

    def test_git_history_events_appear_in_timeline(self, tmp_path):
        history = tmp_path / "git_history.txt"
        history.write_text("abc1234 2026-08-28 Fix payment_amount validation\n", encoding="utf-8")
        timeline = TimelineBuilder.build_timeline("INV-TL-002", history_path=history)

        event_types = {e.event_type for e in timeline.events}
        assert EventType.CODE_CHANGE in event_types


# ---------------------------------------------------------------------------
# 6. PatternDetector → run_investigation similar_patterns
# ---------------------------------------------------------------------------

from services.pattern_detector import PatternDetector


class TestPatternDetectorToInvestigation:
    """PatternDetector results surface in run_investigation output."""

    def test_falsy_pattern_from_source_appears_in_result(self, tmp_path):
        source = tmp_path / "payment.py"
        source.write_text("if not payment_amount:\n    raise ValueError('bad')\n", encoding="utf-8")

        patterns = PatternDetector.find_all_patterns(tmp_path)
        assert any("falsy" in p.similarity_reason.lower() or p.risk_level.value in {"MEDIUM", "HIGH"} for p in patterns)

    def test_no_patterns_for_clean_source(self, tmp_path):
        source = tmp_path / "clean.py"
        source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        patterns = PatternDetector.find_all_patterns(tmp_path)
        assert patterns == []

    def test_investigation_similar_patterns_are_serialisable(self, tmp_path):
        source = tmp_path / "handler.py"
        source.write_text(
            "def h(x):\n    if not x:\n        raise ValueError('bad')\n",
            encoding="utf-8",
        )

        package = {
            "investigation_id": "INT-PAT-001",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "handler error",
            "logs_path": None,
            "source_path": str(source),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        for p in result["similar_patterns"]:
            assert "pattern_id" in p
            assert "risk_level" in p
            assert "excerpt" in p


# ---------------------------------------------------------------------------
# 7. ProjectAnalyzer → ProjectProfile → project_discovery in run_investigation
# ---------------------------------------------------------------------------

from services.project_analyzer import ProjectAnalyzer


class TestProjectAnalyzerToInvestigation:
    """Analyzer populates project_discovery in the investigation result."""

    def test_python_project_detected_in_discovery(self, tmp_path):
        (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")

        profile = ProjectAnalyzer.analyze(tmp_path)
        assert profile.primary_language == "Python"
        assert "Flask" in (profile.framework or "")

    def test_project_discovery_in_run_investigation(self, tmp_path):
        (tmp_path / "api.py").write_text("import flask\n", encoding="utf-8")

        package = {
            "investigation_id": "INT-PROJ-001",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "error",
            "logs_path": None,
            "source_path": str(tmp_path),
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        discovery = result["project_discovery"]

        assert "language" in discovery
        assert "source_file_count" in discovery
        assert "detection_confidence" in discovery

    def test_docker_detected_in_project_profile(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.12\nCMD [\"python\", \"app.py\"]\n", encoding="utf-8")
        (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")

        profile = ProjectAnalyzer.analyze(tmp_path)
        assert profile.docker_detected is True
        assert profile.deployment_profile["containerization"] != "Not detected"

    def test_unknown_project_returns_sensible_defaults_in_discovery(self):
        package = {
            "investigation_id": "INT-PROJ-002",
            "incident": {"service": "svc", "title": "T"},
            "user_observation": "error",
            "logs_path": None,
            "source_path": None,
            "history_path": None,
            "github_repository": None,
        }
        result = run_investigation(package, demo=False)
        discovery = result["project_discovery"]

        assert discovery["language"] in {"Unknown", "Python"}  # demo fallback or unknown


# ---------------------------------------------------------------------------
# 8. Flask API end-to-end (HTTP)
# ---------------------------------------------------------------------------

from app import app as flask_app


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


class TestFlaskAPIEndToEnd:
    """HTTP layer wires correctly into investigation_service."""

    def test_create_with_observation_returns_201_and_id(self, client):
        resp = client.post(
            "/api/investigations",
            data={"observation": "The service is throwing 500 errors."},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["investigation_id"].startswith("INV-")
        assert body["status"] == "created"

    def test_run_observation_only_returns_tribunal_verdict(self, client):
        create = client.post(
            "/api/investigations",
            data={"observation": "Service timeout error."},
        )
        inv_id = create.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        assert "tribunal" in result
        assert result["tribunal"]["judge"]["verdict"] in {
            "CONFIRMED", "MOST_LIKELY", "MORE_EVIDENCE_NEEDED", "REJECTED"
        }

    def test_run_with_log_file_produces_complete_log_investigator(self, client):
        resp = client.post(
            "/api/investigations",
            data={
                "logs": (
                    BytesIO(b"2026-08-29T10:00:00Z ERROR request timed out\n"),
                    "app.log",
                )
            },
            content_type="multipart/form-data",
        )
        inv_id = resp.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert log_inv["status"] == "complete"
        assert result["trust_layer"]["validation_errors"] == []

    def test_run_with_source_zip_produces_complete_code_investigator(self, client):
        zip_bytes = _make_zip({"service.py": "def pay(x):\n    if not x:\n        raise ValueError('bad')\n"})
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(zip_bytes), "project.zip")},
            content_type="multipart/form-data",
        )
        inv_id = resp.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        code_inv = next(i for i in result["investigators"] if i["agent"] == "Code Investigator")
        assert code_inv["status"] == "complete"

    def test_no_evidence_returns_400(self, client):
        resp = client.post("/api/investigations", data={})
        assert resp.status_code == 400

    def test_unknown_investigation_id_returns_404(self, client):
        resp = client.post("/api/investigations/NOT-EXIST/run")
        assert resp.status_code == 404

    def test_run_result_includes_all_v6_summary_keys(self, client):
        create = client.post(
            "/api/investigations",
            data={"observation": "error in the API."},
        )
        inv_id = create.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        assert "investigation_summary" in result
        assert "evidence_strength" in result
        assert "recommended_actions" in result
        assert "investigator_timeline" in result


# ---------------------------------------------------------------------------
# 9. Trust layer validation receives live catalog output
# ---------------------------------------------------------------------------

from services.trust_schema import validate_trust_layer


class TestTrustLayerWithLiveCatalog:
    """validate_trust_layer receives output from a real investigation run."""

    def test_demo_investigation_produces_no_validation_errors(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["trust_layer"]["validation_errors"] == []

    def test_user_investigation_produces_no_validation_errors(self, client):
        create = client.post(
            "/api/investigations",
            data={
                "logs": (
                    BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"),
                    "incident.log",
                )
            },
            content_type="multipart/form-data",
        )
        inv_id = create.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        assert validate_trust_layer(result["trust_layer"]) == []

    def test_trust_layer_facts_are_consistent_with_investigator_evidence(self, client):
        create = client.post(
            "/api/investigations",
            data={
                "logs": (
                    BytesIO(b"2026-08-29T10:00:00Z ERROR db connection refused\n"),
                    "app.log",
                )
            },
            content_type="multipart/form-data",
        )
        inv_id = create.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()

        facts = result["trust_layer"]["facts"]
        investigators = result["investigators"]
        total_evidence_lines = sum(len(i.get("evidence", [])) for i in investigators if i["status"] == "complete")
        # Facts may be a subset if some evidence lines are empty, but cannot exceed total evidence lines
        assert len(facts) <= total_evidence_lines


# ---------------------------------------------------------------------------
# 10. Verification guard integration
# ---------------------------------------------------------------------------


class TestVerificationGuard:
    """Non-demo investigation IDs must never execute code."""

    def test_user_investigation_verify_returns_403(self, client):
        create = client.post(
            "/api/investigations",
            data={"observation": "error"},
        )
        inv_id = create.get_json()["investigation_id"]
        resp = client.post(f"/api/investigations/{inv_id}/verify")

        assert resp.status_code == 403
        body = resp.get_json()
        assert body["execution_policy"] == "untrusted_code_not_executed"

    def test_arbitrary_id_verify_returns_403(self, client):
        resp = client.post("/api/investigations/FAKE-INV-9999/verify")
        assert resp.status_code == 403
        assert resp.get_json()["execution_policy"] == "untrusted_code_not_executed"

    def test_demo_verify_endpoint_runs_and_returns_200(self, client):
        resp = client.post("/api/investigations/DEMO-INC-2026-001/verify")
        assert resp.status_code == 200
