"""
Unit tests for BugSleuth individual components.

Covers:
- models: Evidence, Hypothesis, IncidentTimeline / TimelineEvent, SimilarPattern, ProjectProfile
- services: evidence_catalog, trust_schema, timeline_builder, pattern_detector, investigation_summary
- utils: EvidenceBuilder
- services.file_service: save_log, save_project_zip, create_investigation_dir
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# models.Evidence
# ---------------------------------------------------------------------------

from models.evidence import Evidence, EvidenceStrength, EvidenceType


class TestEvidenceModel:
    def _make(self, **kwargs) -> Evidence:
        defaults = dict(
            evidence_id="EV-00001",
            investigator="Log Investigator",
            source_type=EvidenceType.APPLICATION_LOG,
            source_file="app.log",
        )
        defaults.update(kwargs)
        return Evidence(**defaults)

    def test_defaults_are_set(self):
        ev = self._make()
        assert ev.strength == EvidenceStrength.WEAK
        assert ev.tags == []
        assert ev.line_number is None
        assert ev.excerpt == ""

    def test_to_dict_contains_required_keys(self):
        ev = self._make(excerpt="ERROR request failed", line_number=42, tags=["error"])
        d = ev.to_dict()
        assert d["evidence_id"] == "EV-00001"
        assert d["source_type"] == "application_log"
        assert d["strength"] == "WEAK"
        assert d["line_number"] == 42
        assert d["tags"] == ["error"]

    def test_round_trip_from_dict(self):
        ev = self._make(excerpt="boom", strength=EvidenceStrength.STRONG, tags=["critical"])
        restored = Evidence.from_dict(ev.to_dict())
        assert restored.evidence_id == ev.evidence_id
        assert restored.strength == EvidenceStrength.STRONG
        assert restored.tags == ["critical"]

    def test_all_evidence_types_are_valid_enum_values(self):
        for ev_type in EvidenceType:
            ev = self._make(source_type=ev_type)
            assert ev.to_dict()["source_type"] == ev_type.value

    def test_all_strength_levels_round_trip(self):
        for strength in EvidenceStrength:
            ev = self._make(strength=strength)
            assert Evidence.from_dict(ev.to_dict()).strength == strength


# ---------------------------------------------------------------------------
# models.Hypothesis
# ---------------------------------------------------------------------------

from models.hypothesis import Hypothesis, HypothesisStatus


class TestHypothesisModel:
    def _make(self, **kwargs) -> Hypothesis:
        defaults = dict(hypothesis_id="H-001", description="Falsy check caused failure")
        defaults.update(kwargs)
        return Hypothesis(**defaults)

    def test_confidence_is_clamped_below_zero(self):
        h = self._make(confidence=-5.0)
        assert h.confidence == 0.0

    def test_confidence_is_clamped_above_one(self):
        h = self._make(confidence=99.0)
        assert h.confidence == 1.0

    def test_update_confidence_clamps(self):
        h = self._make(confidence=0.5)
        h.update_confidence(1.5)
        assert h.confidence == 1.0
        h.update_confidence(-0.1)
        assert h.confidence == 0.0

    def test_add_supporting_evidence_no_duplicates(self):
        h = self._make()
        h.add_supporting_evidence("E-001")
        h.add_supporting_evidence("E-001")
        assert h.supporting_evidence.count("E-001") == 1

    def test_add_contradicting_evidence_no_duplicates(self):
        h = self._make()
        h.add_contradicting_evidence("E-002")
        h.add_contradicting_evidence("E-002")
        assert h.contradicting_evidence.count("E-002") == 1

    def test_set_status(self):
        h = self._make()
        h.set_status(HypothesisStatus.CONFIRMED)
        assert h.status == HypothesisStatus.CONFIRMED

    def test_to_dict_confidence_is_rounded(self):
        h = self._make(confidence=0.6666)
        assert h.to_dict()["confidence"] == 0.67

    def test_round_trip_from_dict(self):
        h = self._make(confidence=0.8, status=HypothesisStatus.LEADING)
        h.add_supporting_evidence("E-001")
        restored = Hypothesis.from_dict(h.to_dict())
        assert restored.hypothesis_id == "H-001"
        assert restored.status == HypothesisStatus.LEADING
        assert "E-001" in restored.supporting_evidence


# ---------------------------------------------------------------------------
# models.IncidentTimeline / TimelineEvent
# ---------------------------------------------------------------------------

from models.incident_timeline import IncidentTimeline, TimelineEvent, EventType


class TestIncidentTimeline:
    def _event(self, event_id: str, timestamp: str | None = None, event_type=EventType.ERROR) -> TimelineEvent:
        return TimelineEvent(
            event_id=event_id,
            event_type=event_type,
            description=f"Event {event_id}",
            timestamp=timestamp,
            source="test",
        )

    def test_add_and_count_events(self):
        tl = IncidentTimeline("INV-001")
        tl.add_event(self._event("E1"))
        tl.add_event(self._event("E2"))
        assert len(tl.events) == 2

    def test_get_events_sorted_by_timestamp(self):
        tl = IncidentTimeline("INV-002")
        tl.add_event(self._event("late", "2026-08-29T12:00:00"))
        tl.add_event(self._event("early", "2026-08-29T08:00:00"))
        sorted_ids = [e.event_id for e in tl.get_events_sorted()]
        assert sorted_ids == ["early", "late"]

    def test_undated_events_appear_after_dated(self):
        tl = IncidentTimeline("INV-003")
        tl.add_event(self._event("no-ts", timestamp=None))
        tl.add_event(self._event("dated", "2026-08-29T10:00:00"))
        sorted_ids = [e.event_id for e in tl.get_events_sorted()]
        assert sorted_ids.index("dated") < sorted_ids.index("no-ts")

    def test_to_dict_includes_event_count(self):
        tl = IncidentTimeline("INV-004")
        tl.add_event(self._event("E1"))
        d = tl.to_dict()
        assert d["event_count"] == 1
        assert d["investigation_id"] == "INV-004"

    def test_timeline_event_to_dict(self):
        ev = self._event("E99", "2026-01-01T00:00:00", EventType.DEPLOYMENT)
        d = ev.to_dict()
        assert d["event_type"] == "DEPLOYMENT"
        assert d["event_id"] == "E99"

    def test_round_trip_from_dict(self):
        tl = IncidentTimeline("INV-005")
        tl.add_event(self._event("E1", "2026-08-29T10:00:00", EventType.WARNING))
        restored = IncidentTimeline.from_dict(tl.to_dict())
        assert restored.investigation_id == "INV-005"
        assert len(restored.events) == 1
        assert restored.events[0].event_type == EventType.WARNING

    def test_empty_timeline_sorts_gracefully(self):
        tl = IncidentTimeline("INV-006")
        assert tl.get_events_sorted() == []

    def test_invalid_timestamp_treated_as_undated(self):
        tl = IncidentTimeline("INV-007")
        tl.add_event(self._event("bad-ts", "not-a-date"))
        tl.add_event(self._event("good-ts", "2026-01-01T00:00:00"))
        sorted_ids = [e.event_id for e in tl.get_events_sorted()]
        assert sorted_ids.index("good-ts") < sorted_ids.index("bad-ts")


# ---------------------------------------------------------------------------
# models.SimilarPattern
# ---------------------------------------------------------------------------

from models.similar_patterns import SimilarPattern, RiskLevel


class TestSimilarPatternModel:
    def _make(self, **kwargs) -> SimilarPattern:
        defaults = dict(pattern_id="PAT-00001", source_file="service.py")
        defaults.update(kwargs)
        return SimilarPattern(**defaults)

    def test_confidence_clamped(self):
        p = self._make(match_confidence=5.0)
        assert p.match_confidence == 1.0
        p2 = self._make(match_confidence=-1.0)
        assert p2.match_confidence == 0.0

    def test_to_dict_round_trip(self):
        p = self._make(line_number=10, risk_level=RiskLevel.HIGH, excerpt="if not x:", match_confidence=0.7)
        restored = SimilarPattern.from_dict(p.to_dict())
        assert restored.pattern_id == "PAT-00001"
        assert restored.risk_level == RiskLevel.HIGH
        assert restored.match_confidence == 0.7

    def test_defaults(self):
        p = self._make()
        assert p.risk_level == RiskLevel.LOW
        assert p.excerpt == ""
        assert p.line_number is None


# ---------------------------------------------------------------------------
# models.ProjectProfile
# ---------------------------------------------------------------------------

from models.project_profile import ProjectProfile


class TestProjectProfileModel:
    def test_defaults(self):
        p = ProjectProfile(project_name="MyApp")
        assert p.primary_language == "Unknown"
        assert p.entry_points == []
        assert p.detection_confidence == 1.0
        assert p.deployment_profile["containerization"] == "Not detected"

    def test_detection_confidence_clamped(self):
        p = ProjectProfile(project_name="X", detection_confidence=99.0)
        assert p.detection_confidence == 1.0

    def test_to_dict_and_from_dict_round_trip(self):
        p = ProjectProfile(
            project_name="TestApp",
            primary_language="Python",
            framework="Flask",
            source_file_count=20,
            docker_detected=True,
        )
        restored = ProjectProfile.from_dict(p.to_dict())
        assert restored.project_name == "TestApp"
        assert restored.framework == "Flask"
        assert restored.docker_detected is True
        assert restored.source_file_count == 20


# ---------------------------------------------------------------------------
# services.evidence_catalog
# ---------------------------------------------------------------------------

from services.evidence_catalog import build_evidence_catalog, _source_type


class TestBuildEvidenceCatalog:
    def _investigator(self, agent: str, status: str, evidence: list) -> dict:
        return {"agent": agent, "status": status, "evidence": evidence}

    def test_skips_non_complete_investigators(self):
        investigators = [
            self._investigator("Log Investigator", "unavailable", ["app.log:1: some error"]),
        ]
        assert build_evidence_catalog(investigators) == []

    def test_ids_are_sequential_e_nnn(self):
        investigators = [
            self._investigator("Log Investigator", "complete", ["app.log:1: error", "app.log:2: crash"]),
        ]
        facts = build_evidence_catalog(investigators)
        assert [f["id"] for f in facts] == ["E-001", "E-002"]

    def test_citation_format_is_parsed(self):
        investigators = [
            self._investigator("Log Investigator", "complete", ["app.log:42: request failed"]),
        ]
        fact = build_evidence_catalog(investigators)[0]
        assert fact["source"] == "app.log"
        assert fact["line"] == 42
        assert fact["excerpt"] == "request failed"

    def test_non_citation_evidence_uses_agent_as_source(self):
        investigators = [
            self._investigator("Code Investigator", "complete", ["Falsy check found"]),
        ]
        fact = build_evidence_catalog(investigators)[0]
        assert fact["source"] == "Code Investigator"
        assert fact["line"] is None

    def test_mixed_investigators_combined(self):
        investigators = [
            self._investigator("Log Investigator", "complete", ["a.log:1: err"]),
            self._investigator("Code Investigator", "complete", ["service.py:10: bad code"]),
        ]
        facts = build_evidence_catalog(investigators)
        assert len(facts) == 2
        assert facts[0]["id"] == "E-001"
        assert facts[1]["id"] == "E-002"

    def test_empty_evidence_strings_skipped(self):
        investigators = [
            self._investigator("Log Investigator", "complete", ["", "  ", "app.log:1: real"]),
        ]
        facts = build_evidence_catalog(investigators)
        assert len(facts) == 1

    def test_attribution_is_always_fact(self):
        investigators = [
            self._investigator("Change Investigator", "complete", ["commit abc: deploy"]),
        ]
        fact = build_evidence_catalog(investigators)[0]
        assert fact["attribution"] == "FACT"

    @pytest.mark.parametrize("agent,expected_type", [
        ("Log Investigator", "log"),
        ("Change Investigator", "git"),
        ("Code Investigator", "source"),
        ("Pipeline Investigator", "pipeline"),
        ("Deployment Context Investigator", "deployment"),
        ("Unknown Agent", "other"),
    ])
    def test_source_type_mapping(self, agent: str, expected_type: str):
        assert _source_type(agent) == expected_type


# ---------------------------------------------------------------------------
# services.trust_schema
# ---------------------------------------------------------------------------

from services.trust_schema import validate_trust_layer


class TestValidateTrustLayer:
    def _valid(self) -> dict:
        return {
            "facts": [{"id": "E-001", "type": "log", "attribution": "FACT", "source": "app.log"}],
            "hypothesis": {"id": "H-001", "statement": "x", "evidence_ids": ["E-001"], "causal_chain": []},
            "tribunal": {"prosecutor": {}, "defense": {}, "judge": {}},
            "verification": {"status": "UNAVAILABLE", "execution_policy": "untrusted_code_not_executed"},
        }

    def test_valid_layer_returns_no_errors(self):
        assert validate_trust_layer(self._valid()) == []

    def test_missing_facts_key_is_an_error(self):
        data = self._valid()
        del data["facts"]
        assert len(validate_trust_layer(data)) > 0

    def test_missing_hypothesis_key_is_an_error(self):
        data = self._valid()
        del data["hypothesis"]
        assert len(validate_trust_layer(data)) > 0

    def test_missing_tribunal_key_is_an_error(self):
        data = self._valid()
        del data["tribunal"]
        assert len(validate_trust_layer(data)) > 0

    def test_missing_verification_key_is_an_error(self):
        data = self._valid()
        del data["verification"]
        assert len(validate_trust_layer(data)) > 0

    def test_facts_item_missing_required_field(self):
        data = self._valid()
        data["facts"] = [{"id": "E-001"}]  # missing type, attribution, source
        assert len(validate_trust_layer(data)) > 0

    def test_empty_facts_array_is_valid(self):
        data = self._valid()
        data["facts"] = []
        assert validate_trust_layer(data) == []


# ---------------------------------------------------------------------------
# services.timeline_builder
# ---------------------------------------------------------------------------

from services.timeline_builder import TimelineBuilder


class TestTimelineBuilder:
    def test_build_timeline_empty_paths(self):
        tl = TimelineBuilder.build_timeline("INV-001", logs_path=None, history_path=None)
        assert tl.investigation_id == "INV-001"
        assert tl.events == []

    def test_parse_logs_creates_error_events(self, tmp_path):
        log = tmp_path / "incident.log"
        log.write_text("2026-08-29T10:00:00Z ERROR request failed\n", encoding="utf-8")
        tl = TimelineBuilder.build_timeline("INV-002", logs_path=log)
        assert any(e.event_type.value == "ERROR" for e in tl.events)

    def test_parse_logs_creates_warning_events(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T09:00:00 WARN deprecated method used\n", encoding="utf-8")
        tl = TimelineBuilder.build_timeline("INV-003", logs_path=log)
        assert any(e.event_type.value == "WARNING" for e in tl.events)

    def test_parse_logs_creates_deployment_events(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T08:00:00 INFO deploy version 2.3.0\n", encoding="utf-8")
        tl = TimelineBuilder.build_timeline("INV-DEPLOY", logs_path=log)
        assert any(e.event_type.value == "DEPLOYMENT" for e in tl.events)

    def test_parse_logs_skips_plain_info_lines(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("2026-08-29T10:00:00 INFO server started\n", encoding="utf-8")
        tl = TimelineBuilder.build_timeline("INV-004", logs_path=log)
        # No error/warn/deploy keyword → no events
        assert tl.events == []

    def test_parse_git_history_creates_code_change_events(self, tmp_path):
        history = tmp_path / "git_history.txt"
        history.write_text("abc1234 2026-08-28 Fix validation bug\n", encoding="utf-8")
        tl = TimelineBuilder.build_timeline("INV-005", history_path=history)
        assert any(e.event_type.value == "CODE_CHANGE" for e in tl.events)
        assert any(e.details.get("commit") == "abc1234" for e in tl.events)

    def test_add_incident_event(self):
        from models.incident_timeline import IncidentTimeline
        tl = IncidentTimeline("INV-006")
        TimelineBuilder.add_incident_event(tl, "2026-08-29T12:00:00")
        assert any(e.event_id == "INCIDENT-001" for e in tl.events)

    def test_add_investigation_start(self):
        from models.incident_timeline import IncidentTimeline
        tl = IncidentTimeline("INV-007")
        TimelineBuilder.add_investigation_start(tl)
        assert any(e.event_id == "INVESTIGATION-001" for e in tl.events)

    def test_nonexistent_log_file_returns_empty_timeline(self, tmp_path):
        tl = TimelineBuilder.build_timeline("INV-008", logs_path=tmp_path / "missing.log")
        assert tl.events == []


# ---------------------------------------------------------------------------
# services.pattern_detector
# ---------------------------------------------------------------------------

from services.pattern_detector import PatternDetector


class TestPatternDetector:
    def test_returns_empty_for_none_path(self):
        assert PatternDetector.find_similar_patterns(None) == []

    def test_returns_empty_for_nonexistent_path(self, tmp_path):
        assert PatternDetector.find_similar_patterns(tmp_path / "nope") == []

    def test_detects_falsy_value_validation(self, tmp_path):
        f = tmp_path / "service.py"
        f.write_text("if not payment_amount:\n    raise ValueError('bad')\n", encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "falsy_value_validation")
        assert len(patterns) >= 1
        assert patterns[0].risk_level.value == "MEDIUM"

    def test_detects_catch_all_exception(self, tmp_path):
        f = tmp_path / "handlers.py"
        f.write_text("try:\n    process()\nexcept:\n    pass\n", encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "catch_all_exception")
        assert len(patterns) >= 1

    def test_detects_silent_failure(self, tmp_path):
        # The silent_failure regex `except\s*:[\s\n]*pass` is evaluated per-line,
        # so it only matches when `except:` and `pass` appear on the same source line.
        f = tmp_path / "util.py"
        f.write_text("try:\n    risky()\nexcept: pass\n", encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "silent_failure")
        assert len(patterns) >= 1
        assert patterns[0].risk_level.value == "HIGH"

    def test_max_results_is_respected(self, tmp_path):
        lines = "\n".join(f"if not x_{i}:" for i in range(20))
        (tmp_path / "big.py").write_text(lines, encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "falsy_value_validation", max_results=3)
        assert len(patterns) <= 3

    def test_unknown_pattern_type_returns_empty(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        assert PatternDetector.find_similar_patterns(tmp_path, "nonexistent_pattern") == []

    def test_find_all_patterns_combines_types(self, tmp_path):
        (tmp_path / "mixed.py").write_text(
            "if not amount:\n    raise ValueError()\ntry:\n    go()\nexcept:\n    pass\n",
            encoding="utf-8",
        )
        patterns = PatternDetector.find_all_patterns(tmp_path)
        types = {p.similarity_reason for p in patterns}
        assert len(types) >= 2

    def test_pattern_ids_are_unique(self, tmp_path):
        lines = "\n".join(f"if not v_{i}:" for i in range(5))
        (tmp_path / "f.py").write_text(lines, encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "falsy_value_validation")
        ids = [p.pattern_id for p in patterns]
        assert len(ids) == len(set(ids))

    def test_excerpt_is_truncated_to_150_chars(self, tmp_path):
        long_line = "if not " + "x" * 200 + ":"
        (tmp_path / "long.py").write_text(long_line + "\n", encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(tmp_path, "falsy_value_validation")
        assert all(len(p.excerpt) <= 150 for p in patterns)

    def test_single_file_path_is_accepted(self, tmp_path):
        f = tmp_path / "single.py"
        f.write_text("if not value:\n    pass\n", encoding="utf-8")
        patterns = PatternDetector.find_similar_patterns(f, "falsy_value_validation")
        assert len(patterns) >= 1


# ---------------------------------------------------------------------------
# services.investigation_summary helpers
# ---------------------------------------------------------------------------

from services.investigation_summary import (
    InvestigationReadiness,
    EvidenceStrength as InvEvidenceStrength,
    InvestigationActivityTimeline,
    _classify_readiness,
    _classify_strength,
    _determine_verification_status,
)


class TestInvestigationReadiness:
    def test_full_package_gives_high_score(self):
        pkg = {
            "source_path": "/some/path",
            "logs_path": "/some/app.log",
            "history_path": "/some/git.txt",
            "user_observation": "traceback exception at line 5 error",
        }
        result = InvestigationReadiness.calculate(pkg)
        assert result["readiness_score"] == 100
        assert result["readiness_level"] == "HIGH"

    def test_empty_package_gives_zero(self):
        result = InvestigationReadiness.calculate({})
        assert result["readiness_score"] == 0
        assert result["readiness_level"] == "LIMITED"

    def test_logs_only_gives_partial_score(self):
        result = InvestigationReadiness.calculate({"logs_path": "/app.log"})
        assert 0 < result["readiness_score"] < 100

    def test_missing_list_includes_source_code_when_absent(self):
        result = InvestigationReadiness.calculate({})
        missing = result["missing_evidence"]
        assert any("Source Code" in item for item in missing)

    def test_available_list_reflects_provided_evidence(self):
        result = InvestigationReadiness.calculate({"source_path": "/code", "logs_path": "/log"})
        assert "Source Code" in result["available_evidence"]
        assert "Application Logs" in result["available_evidence"]

    def test_classify_readiness_thresholds(self):
        assert _classify_readiness(75) == "HIGH"
        assert _classify_readiness(50) == "MODERATE"
        assert _classify_readiness(49) == "LIMITED"
        assert _classify_readiness(0) == "LIMITED"


class TestEvidenceStrengthService:
    def _investigator(self, agent: str, status: str, findings: list, confidence: float = 0.8) -> dict:
        return {"agent": agent, "status": status, "findings": findings, "confidence": confidence}

    def test_all_unavailable_gives_zero_percent(self):
        investigators = [self._investigator("Log Investigator", "unavailable", [])]
        result = InvEvidenceStrength.calculate(investigators)
        assert result["percentage"] == 0
        assert result["strength_level"] == "INSUFFICIENT"

    def test_complete_with_findings_gives_positive_score(self):
        investigators = [self._investigator("Code Investigator", "complete", ["f1", "f2", "f3"])]
        result = InvEvidenceStrength.calculate(investigators)
        assert result["percentage"] > 0
        assert result["sources_analyzed"] == 1

    def test_classify_strength_thresholds(self):
        assert _classify_strength(90) == "VERY STRONG"
        assert _classify_strength(75) == "STRONG"
        assert _classify_strength(50) == "MODERATE"
        assert _classify_strength(25) == "LIMITED"
        assert _classify_strength(0) == "INSUFFICIENT"

    def test_mixed_investigators_counted_correctly(self):
        investigators = [
            self._investigator("Log Investigator", "complete", ["e1"]),
            self._investigator("Code Investigator", "unavailable", []),
        ]
        result = InvEvidenceStrength.calculate(investigators)
        assert result["sources_analyzed"] == 1
        assert result["total_sources"] == 2


class TestInvestigationActivityTimeline:
    def test_timeline_starts_with_project_intelligence(self):
        tl = InvestigationActivityTimeline.generate([])
        assert tl[0]["agent"] == "Project Intelligence"

    def test_timeline_ends_with_tribunal_review(self):
        tl = InvestigationActivityTimeline.generate([])
        assert tl[-1]["agent"] == "Tribunal Review"

    def test_complete_investigator_shows_correct_icon(self):
        investigators = [{"agent": "Log Investigator", "status": "complete", "findings": ["e1"]}]
        tl = InvestigationActivityTimeline.generate(investigators)
        log_entry = next(e for e in tl if e.get("full_agent_name") == "Log Investigator")
        assert log_entry["icon"] == "✓"
        assert log_entry["findings_count"] == 1

    def test_unavailable_investigator_shows_x_icon(self):
        investigators = [{"agent": "Log Investigator", "status": "unavailable", "findings": []}]
        tl = InvestigationActivityTimeline.generate(investigators)
        log_entry = next(e for e in tl if e.get("full_agent_name") == "Log Investigator")
        assert log_entry["icon"] == "✗"

    def test_agent_display_name_mapping(self):
        investigators = [{"agent": "Change Investigator", "status": "complete", "findings": []}]
        tl = InvestigationActivityTimeline.generate(investigators)
        entry = next(e for e in tl if e.get("full_agent_name") == "Change Investigator")
        assert entry["agent"] == "Change History"


class TestDetermineVerificationStatus:
    def test_demo_confirmed_is_verified(self):
        verdict = {"verdict": "CONFIRMED"}
        assert _determine_verification_status(verdict, {}, demo=True) == "VERIFIED"

    def test_demo_most_likely_is_partially_verified(self):
        verdict = {"verdict": "MOST_LIKELY"}
        assert _determine_verification_status(verdict, {}, demo=True) == "PARTIALLY_VERIFIED"

    def test_demo_other_verdict_is_not_verified(self):
        verdict = {"verdict": "MORE_EVIDENCE_NEEDED"}
        assert _determine_verification_status(verdict, {}, demo=True) == "NOT_VERIFIED"

    def test_user_investigation_is_not_verified(self):
        verdict = {"verdict": "MOST_LIKELY", "reason": ""}
        assert _determine_verification_status(verdict, {}, demo=False) == "NOT_VERIFIED"


# ---------------------------------------------------------------------------
# utils.EvidenceBuilder
# ---------------------------------------------------------------------------

from utils.evidence_builder import EvidenceBuilder
from models.evidence import EvidenceStrength, EvidenceType


class TestEvidenceBuilder:
    def test_ids_are_sequential(self):
        builder = EvidenceBuilder()
        ev1 = builder.create_from_log_entry("Log Investigator", "app.log", "ERROR boom")
        ev2 = builder.create_from_log_entry("Log Investigator", "app.log", "WARN slow")
        assert ev1.evidence_id == "EV-00001"
        assert ev2.evidence_id == "EV-00002"

    def test_create_from_code_line(self):
        builder = EvidenceBuilder()
        ev = builder.create_from_code_line(
            "Code Investigator", "service.py", "if not value:", line_number=10, tags=["bug"]
        )
        assert ev.source_type == EvidenceType.SOURCE_CODE
        assert ev.line_number == 10
        assert "bug" in ev.tags

    def test_create_from_log_entry(self):
        builder = EvidenceBuilder()
        ev = builder.create_from_log_entry("Log Investigator", "app.log", "2026 ERROR crash")
        assert ev.source_type == EvidenceType.APPLICATION_LOG
        assert ev.source_file == "app.log"

    def test_create_from_git_history(self):
        builder = EvidenceBuilder()
        ev = builder.create_from_git_history("Change Investigator", "abc1234", "Fix validation")
        assert ev.source_type == EvidenceType.GIT_HISTORY
        assert ev.source_file == "abc1234"
        assert ev.excerpt == "Fix validation"

    def test_create_generic(self):
        builder = EvidenceBuilder()
        ev = builder.create_generic(
            "Pipeline Investigator",
            EvidenceType.TEST_FAILURE,
            "ci.yml",
            excerpt="tests failed",
            strength=EvidenceStrength.STRONG,
            line_number=5,
        )
        assert ev.source_type == EvidenceType.TEST_FAILURE
        assert ev.strength == EvidenceStrength.STRONG
        assert ev.line_number == 5

    def test_ids_reset_across_instances(self):
        b1 = EvidenceBuilder()
        b1.create_from_log_entry("A", "a.log", "x")
        b2 = EvidenceBuilder()
        ev = b2.create_from_log_entry("A", "a.log", "x")
        assert ev.evidence_id == "EV-00001"

    def test_default_strength_is_weak(self):
        builder = EvidenceBuilder()
        ev = builder.create_from_log_entry("Log Investigator", "app.log", "info msg")
        assert ev.strength == EvidenceStrength.WEAK

    def test_empty_tags_default(self):
        builder = EvidenceBuilder()
        ev = builder.create_from_code_line("Code Investigator", "f.py", "line")
        assert ev.tags == []


# ---------------------------------------------------------------------------
# services.file_service
# ---------------------------------------------------------------------------

from services.file_service import (
    create_investigation_dir,
    save_log,
    save_project_zip,
)


class TestCreateInvestigationDir:
    def test_creates_directory_under_root(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        assert path.exists()
        assert path.is_dir()
        assert path.parent == tmp_path

    def test_directory_name_starts_with_inv(self, tmp_path):
        path = create_investigation_dir(tmp_path)
        assert path.name.startswith("INV-")

    def test_two_calls_produce_different_dirs(self, tmp_path):
        p1 = create_investigation_dir(tmp_path)
        p2 = create_investigation_dir(tmp_path)
        assert p1 != p2


class FakeUpload:
    """Minimal werkzeug FileStorage stand-in for unit testing."""

    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data
        self.content_length = len(data)
        self._buf = BytesIO(data)

    def save(self, dst: Path):
        dst.write_bytes(self._data)


class TestSaveLog:
    def test_saves_valid_log_file(self, tmp_path):
        upload = FakeUpload("app.log", b"2026 ERROR crash\n")
        name = save_log(upload, tmp_path)
        assert name == "app.log"
        assert (tmp_path / "app.log").exists()

    def test_saves_valid_txt_file(self, tmp_path):
        upload = FakeUpload("incident.txt", b"some log content\n")
        name = save_log(upload, tmp_path)
        assert name == "incident.txt"

    def test_rejects_unsupported_extension(self, tmp_path):
        upload = FakeUpload("archive.zip", b"data")
        with pytest.raises(ValueError, match="not supported"):
            save_log(upload, tmp_path)

    def test_rejects_empty_filename(self, tmp_path):
        upload = FakeUpload("", b"data")
        with pytest.raises(ValueError):
            save_log(upload, tmp_path)

    def test_rejects_oversized_file(self, tmp_path):
        big_data = b"x" * (2 * 1024 * 1024 + 1)
        upload = FakeUpload("large.log", big_data)
        with pytest.raises(ValueError, match="too large"):
            save_log(upload, tmp_path)


class TestSaveProjectZip:
    def _make_zip(self, entries: dict[str, str]) -> bytes:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in entries.items():
                zf.writestr(name, content)
        return buf.getvalue()

    def test_saves_valid_zip(self, tmp_path):
        data = self._make_zip({"service.py": "x = 1"})
        upload = FakeUpload("project.zip", data)
        name = save_project_zip(upload, tmp_path)
        assert name == "project.zip"
        assert (tmp_path / "source" / "service.py").exists()

    def test_rejects_non_zip_extension(self, tmp_path):
        upload = FakeUpload("project.tar", b"data")
        with pytest.raises(ValueError, match="not supported"):
            save_project_zip(upload, tmp_path)

    def test_rejects_path_traversal_zip(self, tmp_path):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../evil.py", "print('evil')")
        upload = FakeUpload("attack.zip", buf.getvalue())
        with pytest.raises(ValueError):
            save_project_zip(upload, tmp_path)

    def test_archive_file_removed_after_extraction(self, tmp_path):
        data = self._make_zip({"main.py": "pass"})
        upload = FakeUpload("project.zip", data)
        save_project_zip(upload, tmp_path)
        assert not (tmp_path / "project.zip").exists()

    def test_rejects_empty_filename(self, tmp_path):
        upload = FakeUpload("", b"data")
        with pytest.raises(ValueError):
            save_project_zip(upload, tmp_path)
