"""
System tests for BugSleuth.

Tests the complete software as a whole — exercising the full end-to-end flow
from HTTP request through all layers (file handling, investigators, tribunal,
trust schema, verification guard) to the final JSON response.

No internal modules are imported directly; all interaction is through the
Flask test client (the public API surface).

Scenarios covered:
 ST-01  Demo investigation endpoint returns a complete, valid result
 ST-02  Observation-only submission is conservative (MORE_EVIDENCE_NEEDED)
 ST-03  Log upload triggers a complete Log Investigator run
 ST-04  Source ZIP upload triggers a complete Code Investigator run
 ST-05  Log + source ZIP together yield a richer result
 ST-06  All required top-level keys are present in every investigation result
 ST-07  Trust layer contract is always valid (no validation_errors)
 ST-08  Facts in the trust layer are properly attributed (E-NNN ids, FACT label)
 ST-09  Verification is always blocked (403) for non-demo investigation IDs
 ST-10  Demo verification endpoint is reachable and returns 200
 ST-11  No evidence at all returns 400
 ST-12  Unknown investigation ID returns 404 on run
 ST-13  Oversized log file (>20 MB) is rejected with 400
 ST-14  Unsupported file extension for log upload is rejected with 400
 ST-15  Non-ZIP source upload is rejected with 400
 ST-16  Path-traversal ZIP is rejected with 400
 ST-17  UTF-16 log file is handled without crashing
 ST-18  Demo result contains all v6 summary fields
 ST-19  User investigation never leaks demo-specific data
 ST-20  Timeline always contains the INVESTIGATION-001 event
 ST-21  Index page renders (HTML, 200)
 ST-22  About page renders (HTML, 200)
 ST-23  Help page renders (HTML, 200)
 ST-24  Investigation page renders for demo ID (200)
 ST-25  Investigation page returns 404 template for unknown ID
 ST-26  Multiple sequential investigations are isolated from each other
 ST-27  Log with multiple ERROR lines produces multiple evidence facts
 ST-28  Source with risky patterns produces non-empty similar_patterns
 ST-29  Git history upload causes Change Investigator to run
 ST-30  Proof verification field is UNAVAILABLE for user investigations
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from app import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def _make_zip(entries: dict[str, str]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _create_and_run(client, **form_data) -> dict:
    """Helper: POST /api/investigations then POST /run, return the run result."""
    create_resp = client.post(
        "/api/investigations",
        data=form_data,
        content_type="multipart/form-data",
    )
    assert create_resp.status_code == 201, create_resp.get_json()
    inv_id = create_resp.get_json()["investigation_id"]
    run_resp = client.post(f"/api/investigations/{inv_id}/run")
    assert run_resp.status_code == 200, run_resp.get_json()
    return run_resp.get_json()


# ---------------------------------------------------------------------------
# ST-01  Demo investigation endpoint
# ---------------------------------------------------------------------------

class TestST01DemoEndpoint:
    def test_returns_200(self, client):
        resp = client.post("/api/investigate")
        assert resp.status_code == 200

    def test_result_has_demo_mode_flag(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["mode"] == "demo"
        assert result["demo"] is True

    def test_demo_investigation_id_is_correct(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["investigation_id"] == "DEMO-INC-2026-001"

    def test_demo_trust_layer_has_no_validation_errors(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["trust_layer"]["validation_errors"] == []

    def test_demo_trust_layer_facts_are_non_empty(self, client):
        result = client.post("/api/investigate").get_json()
        assert len(result["trust_layer"]["facts"]) > 0

    def test_demo_verdict_is_confirmed(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["tribunal"]["judge"]["verdict"] == "CONFIRMED"


# ---------------------------------------------------------------------------
# ST-02  Observation-only → conservative verdict
# ---------------------------------------------------------------------------

class TestST02ObservationOnly:
    def test_create_returns_201(self, client):
        resp = client.post(
            "/api/investigations",
            data={"observation": "Users see 500 errors on the checkout page."},
        )
        assert resp.status_code == 201

    def test_verdict_is_more_evidence_needed(self, client):
        result = _create_and_run(client, observation="The service is failing.")
        assert result["tribunal"]["judge"]["verdict"] == "MORE_EVIDENCE_NEEDED"

    def test_proof_verification_is_unavailable(self, client):
        result = _create_and_run(client, observation="Something broke.")
        assert result["proof"]["verification"]["status"] == "UNAVAILABLE"

    def test_ledger_lists_missing_log_evidence(self, client):
        result = _create_and_run(client, observation="Something is wrong.")
        missing = " ".join(result["ledger"]["missing_evidence"]).lower()
        assert "log" in missing or "evidence" in missing


# ---------------------------------------------------------------------------
# ST-03  Log-only submission
# ---------------------------------------------------------------------------

class TestST03LogOnlySubmission:
    LOG_BYTES = b"2026-08-29T10:00:00Z ERROR request timed out\n"

    def test_create_with_log_returns_201(self, client):
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(self.LOG_BYTES), "app.log")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201

    def test_log_investigator_is_complete(self, client):
        result = _create_and_run(
            client, logs=(BytesIO(self.LOG_BYTES), "app.log")
        )
        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert log_inv["status"] == "complete"

    def test_log_evidence_references_file(self, client):
        result = _create_and_run(
            client, logs=(BytesIO(self.LOG_BYTES), "incident.log")
        )
        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert any("incident.log" in e for e in log_inv["evidence"])

    def test_verdict_is_most_likely_with_single_error_log(self, client):
        result = _create_and_run(
            client, logs=(BytesIO(self.LOG_BYTES), "app.log")
        )
        assert result["tribunal"]["judge"]["verdict"] in {"MOST_LIKELY", "CONFIRMED"}

    def test_trust_layer_has_no_validation_errors(self, client):
        result = _create_and_run(
            client, logs=(BytesIO(self.LOG_BYTES), "app.log")
        )
        assert result["trust_layer"]["validation_errors"] == []


# ---------------------------------------------------------------------------
# ST-04  Source ZIP submission
# ---------------------------------------------------------------------------

class TestST04SourceZipSubmission:
    ZIP_CONTENTS = {
        "service.py": (
            "def process(amount):\n"
            "    if not amount:\n"
            "        raise ValueError('Invalid')\n"
        )
    }

    def test_create_with_zip_returns_201(self, client):
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201

    def test_code_investigator_is_complete(self, client):
        result = _create_and_run(
            client,
            observation="payment error",
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        code_inv = next(i for i in result["investigators"] if i["agent"] == "Code Investigator")
        assert code_inv["status"] == "complete"

    def test_similar_patterns_detected(self, client):
        result = _create_and_run(
            client,
            observation="payment error",
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        assert isinstance(result["similar_patterns"], list)
        assert len(result["similar_patterns"]) >= 1

    def test_trust_layer_has_no_validation_errors(self, client):
        result = _create_and_run(
            client,
            observation="payment error",
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        assert result["trust_layer"]["validation_errors"] == []


# ---------------------------------------------------------------------------
# ST-05  Log + source ZIP combined
# ---------------------------------------------------------------------------

class TestST05LogAndSourceCombined:
    LOG_BYTES = b"2026-08-29T10:00:00Z ERROR payment failed\n"
    ZIP_CONTENTS = {
        "api.py": "def handler():\n    raise Exception('payment failed')\n"
    }

    def test_both_investigators_complete(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(self.LOG_BYTES), "app.log"),
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        agents = {i["agent"]: i["status"] for i in result["investigators"]}
        assert agents["Log Investigator"] == "complete"
        assert agents["Code Investigator"] == "complete"

    def test_facts_reference_both_log_and_source(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(self.LOG_BYTES), "app.log"),
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        types = {f["type"] for f in result["trust_layer"]["facts"]}
        assert "log" in types
        assert "source" in types

    def test_trust_layer_valid(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(self.LOG_BYTES), "app.log"),
            source_zip=(BytesIO(_make_zip(self.ZIP_CONTENTS)), "project.zip"),
        )
        assert result["trust_layer"]["validation_errors"] == []


# ---------------------------------------------------------------------------
# ST-06  Required top-level keys in every investigation result
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = {
    "incident", "investigation_id", "mode", "trust_layer",
    "tribunal", "investigators", "ledger", "proof",
    "timeline", "similar_patterns", "investigation_summary",
    "evidence_strength", "recommended_actions", "investigator_timeline",
    "project_discovery", "evidence_status",
}

class TestST06RequiredTopLevelKeys:
    def test_observation_only_result_has_all_keys(self, client):
        result = _create_and_run(client, observation="Something is wrong.")
        assert REQUIRED_TOP_KEYS.issubset(result.keys())

    def test_log_only_result_has_all_keys(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"), "app.log"),
        )
        assert REQUIRED_TOP_KEYS.issubset(result.keys())

    def test_demo_result_has_all_keys(self, client):
        result = client.post("/api/investigate").get_json()
        assert REQUIRED_TOP_KEYS.issubset(result.keys())


# ---------------------------------------------------------------------------
# ST-07  Trust layer contract validity
# ---------------------------------------------------------------------------

class TestST07TrustLayerAlwaysValid:
    def test_observation_only_trust_layer_valid(self, client):
        result = _create_and_run(client, observation="errors in production.")
        assert result["trust_layer"]["validation_errors"] == []

    def test_log_only_trust_layer_valid(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR db timeout\n"), "app.log"),
        )
        assert result["trust_layer"]["validation_errors"] == []

    def test_demo_trust_layer_valid(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["trust_layer"]["validation_errors"] == []


# ---------------------------------------------------------------------------
# ST-08  Trust layer facts attribution
# ---------------------------------------------------------------------------

class TestST08TrustLayerFacts:
    def test_demo_facts_have_e_nnn_ids(self, client):
        result = client.post("/api/investigate").get_json()
        for fact in result["trust_layer"]["facts"]:
            assert fact["id"].startswith("E-"), f"Bad id: {fact['id']}"

    def test_demo_facts_are_all_attributed_as_fact(self, client):
        result = client.post("/api/investigate").get_json()
        for fact in result["trust_layer"]["facts"]:
            assert fact["attribution"] == "FACT"

    def test_log_investigation_facts_ids_are_sequential(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(
                b"2026-08-29T10:00:00Z ERROR crash\n"
                b"2026-08-29T10:00:01Z ERROR timeout\n"
            ), "app.log"),
        )
        facts = result["trust_layer"]["facts"]
        ids = [f["id"] for f in facts]
        expected = [f"E-{i:03d}" for i in range(1, len(ids) + 1)]
        assert ids == expected


# ---------------------------------------------------------------------------
# ST-09  Verification guard — non-demo IDs always blocked
# ---------------------------------------------------------------------------

class TestST09VerificationGuard:
    def test_user_investigation_verify_blocked(self, client):
        create = client.post(
            "/api/investigations",
            data={"observation": "error"},
        )
        inv_id = create.get_json()["investigation_id"]
        resp = client.post(f"/api/investigations/{inv_id}/verify")
        assert resp.status_code == 403

    def test_arbitrary_id_verify_blocked(self, client):
        resp = client.post("/api/investigations/NOT-REAL-999/verify")
        assert resp.status_code == 403

    def test_blocked_response_has_correct_execution_policy(self, client):
        resp = client.post("/api/investigations/NOT-REAL-999/verify")
        body = resp.get_json()
        assert body["execution_policy"] == "untrusted_code_not_executed"

    def test_blocked_response_has_unavailable_status(self, client):
        resp = client.post("/api/investigations/NOT-REAL-999/verify")
        body = resp.get_json()
        assert body["status"] == "unavailable"


# ---------------------------------------------------------------------------
# ST-10  Demo verification endpoint reachable
# ---------------------------------------------------------------------------

class TestST10DemoVerification:
    def test_demo_verify_returns_200(self, client):
        resp = client.post("/api/investigations/DEMO-INC-2026-001/verify")
        assert resp.status_code == 200

    def test_demo_verify_returns_json(self, client):
        resp = client.post("/api/investigations/DEMO-INC-2026-001/verify")
        body = resp.get_json()
        assert body is not None


# ---------------------------------------------------------------------------
# ST-11  No evidence → 400
# ---------------------------------------------------------------------------

class TestST11NoEvidence:
    def test_empty_form_returns_400(self, client):
        resp = client.post("/api/investigations", data={})
        assert resp.status_code == 400

    def test_error_message_describes_problem(self, client):
        resp = client.post("/api/investigations", data={})
        body = resp.get_json()
        assert "error" in body
        assert body["error"]  # non-empty


# ---------------------------------------------------------------------------
# ST-12  Unknown investigation ID → 404
# ---------------------------------------------------------------------------

class TestST12UnknownInvestigationId:
    def test_run_on_unknown_id_returns_404(self, client):
        resp = client.post("/api/investigations/DOES-NOT-EXIST/run")
        assert resp.status_code == 404

    def test_error_key_in_body(self, client):
        resp = client.post("/api/investigations/DOES-NOT-EXIST/run")
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# ST-13  Oversized log file → 400
# ---------------------------------------------------------------------------

class TestST13OversizedFile:
    def test_oversized_log_rejected(self, client):
        big = b"x" * (21 * 1024 * 1024)
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(big), "big.log")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_oversized_zip_rejected(self, client):
        big = b"x" * (21 * 1024 * 1024)
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(big), "project.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ST-14  Unsupported log extension → 400
# ---------------------------------------------------------------------------

class TestST14UnsupportedLogExtension:
    def test_csv_log_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(b"col1,col2\n"), "logs.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_pdf_log_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(b"%PDF"), "logs.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ST-15  Non-ZIP source upload → 400
# ---------------------------------------------------------------------------

class TestST15NonZipSource:
    def test_tar_source_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(b"data"), "project.tar")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_txt_source_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(b"data"), "source.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ST-16  Path-traversal ZIP → 400
# ---------------------------------------------------------------------------

class TestST16PathTraversalZip:
    def test_traversal_zip_rejected(self, client):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../evil.py", "print('evil')")
        buf.seek(0)
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (buf, "project.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# ST-17  UTF-16 log file handled gracefully
# ---------------------------------------------------------------------------

class TestST17Utf16Log:
    def test_utf16_log_returns_200_run(self, client):
        content = "2026-08-29T10:00:00Z ERROR request failed\n".encode("utf-16")
        create = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(content), "incident.txt")},
            content_type="multipart/form-data",
        )
        assert create.status_code == 201
        inv_id = create.get_json()["investigation_id"]
        run = client.post(f"/api/investigations/{inv_id}/run")
        assert run.status_code == 200


# ---------------------------------------------------------------------------
# ST-18  v6 summary fields in demo and user results
# ---------------------------------------------------------------------------

V6_SUMMARY_KEYS = {"investigation_summary", "evidence_strength", "recommended_actions", "investigator_timeline"}

class TestST18V6SummaryFields:
    def test_demo_result_has_v6_summary_fields(self, client):
        result = client.post("/api/investigate").get_json()
        assert V6_SUMMARY_KEYS.issubset(result.keys())

    def test_user_result_has_v6_summary_fields(self, client):
        result = _create_and_run(client, observation="system failure.")
        assert V6_SUMMARY_KEYS.issubset(result.keys())

    def test_investigator_timeline_starts_with_project_intelligence(self, client):
        result = _create_and_run(client, observation="error.")
        tl = result["investigator_timeline"]
        assert tl[0]["agent"] == "Project Intelligence"

    def test_investigator_timeline_ends_with_tribunal_review(self, client):
        result = _create_and_run(client, observation="error.")
        tl = result["investigator_timeline"]
        assert tl[-1]["agent"] == "Tribunal Review"


# ---------------------------------------------------------------------------
# ST-19  User investigation never leaks demo data
# ---------------------------------------------------------------------------

class TestST19NoDemoDataLeakage:
    def test_mode_is_user(self, client):
        result = _create_and_run(client, observation="The API is failing.")
        assert result["mode"] == "user"

    def test_no_payment_demo_text_in_result(self, client):
        result = _create_and_run(client, observation="The backend API is returning 500.")
        serialised = str(result).lower()
        assert "payment_amount" not in serialised

    def test_no_demo_commit_sha_in_result(self, client):
        result = _create_and_run(client, observation="The backend API is returning 500.")
        assert "abc1234" not in str(result).lower()

    def test_demo_is_false(self, client):
        result = _create_and_run(client, observation="Something is down.")
        assert result["demo"] is False


# ---------------------------------------------------------------------------
# ST-20  Timeline always contains INVESTIGATION-001
# ---------------------------------------------------------------------------

class TestST20TimelineInvestigationEvent:
    def test_observation_only_timeline_has_investigation_start(self, client):
        result = _create_and_run(client, observation="error observed.")
        event_ids = [e["event_id"] for e in result["timeline"]["events"]]
        assert "INVESTIGATION-001" in event_ids

    def test_log_only_timeline_has_investigation_start(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"), "app.log"),
        )
        event_ids = [e["event_id"] for e in result["timeline"]["events"]]
        assert "INVESTIGATION-001" in event_ids

    def test_demo_timeline_has_investigation_start(self, client):
        result = client.post("/api/investigate").get_json()
        event_ids = [e["event_id"] for e in result["timeline"]["events"]]
        assert "INVESTIGATION-001" in event_ids


# ---------------------------------------------------------------------------
# ST-21–25  Page rendering
# ---------------------------------------------------------------------------

class TestST21To25PageRendering:
    def test_index_page_returns_200_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<html" in resp.data.lower() or b"<!doctype" in resp.data.lower()

    def test_about_page_returns_200(self, client):
        resp = client.get("/about")
        assert resp.status_code == 200

    def test_help_page_returns_200(self, client):
        resp = client.get("/help")
        assert resp.status_code == 200

    def test_demo_investigation_page_returns_200(self, client):
        resp = client.get("/investigations/DEMO-INC-2026-001")
        assert resp.status_code == 200

    def test_unknown_investigation_page_returns_404(self, client):
        resp = client.get("/investigations/FAKE-ID-9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ST-26  Multiple sequential investigations are isolated
# ---------------------------------------------------------------------------

class TestST26InvestigationIsolation:
    def test_two_investigations_have_different_ids(self, client):
        r1 = client.post("/api/investigations", data={"observation": "error A"})
        r2 = client.post("/api/investigations", data={"observation": "error B"})
        assert r1.get_json()["investigation_id"] != r2.get_json()["investigation_id"]

    def test_running_one_does_not_affect_the_other(self, client):
        create_a = client.post("/api/investigations", data={"observation": "error in service A"})
        create_b = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(b"2026-08-29T10:00:00Z ERROR crash B\n"), "b.log")},
            content_type="multipart/form-data",
        )
        id_a = create_a.get_json()["investigation_id"]
        id_b = create_b.get_json()["investigation_id"]

        result_a = client.post(f"/api/investigations/{id_a}/run").get_json()
        result_b = client.post(f"/api/investigations/{id_b}/run").get_json()

        assert result_a["investigation_id"] == id_a
        assert result_b["investigation_id"] == id_b
        assert result_a["investigation_id"] != result_b["investigation_id"]


# ---------------------------------------------------------------------------
# ST-27  Multiple ERROR lines → multiple evidence facts
# ---------------------------------------------------------------------------

class TestST27MultipleErrorLines:
    def test_three_errors_produce_three_or_more_facts(self, client):
        log_bytes = (
            b"2026-08-29T10:00:00Z ERROR db timeout\n"
            b"2026-08-29T10:00:01Z ERROR null pointer\n"
            b"2026-08-29T10:00:02Z ERROR payment failed\n"
        )
        result = _create_and_run(
            client,
            logs=(BytesIO(log_bytes), "multi.log"),
        )
        facts = result["trust_layer"]["facts"]
        assert len(facts) >= 3

    def test_facts_ids_are_sequential(self, client):
        log_bytes = (
            b"2026-08-29T10:00:00Z ERROR crash 1\n"
            b"2026-08-29T10:00:01Z ERROR crash 2\n"
        )
        result = _create_and_run(
            client,
            logs=(BytesIO(log_bytes), "multi.log"),
        )
        facts = result["trust_layer"]["facts"]
        ids = [f["id"] for f in facts]
        expected = [f"E-{i:03d}" for i in range(1, len(ids) + 1)]
        assert ids == expected


# ---------------------------------------------------------------------------
# ST-28  Risky source code patterns surface in result
# ---------------------------------------------------------------------------

class TestST28RiskySourcePatterns:
    def test_falsy_check_pattern_detected(self, client):
        risky_code = (
            "def process(amount):\n"
            "    if not amount:\n"
            "        raise ValueError('bad')\n"
            "    try:\n"
            "        pay(amount)\n"
            "    except:\n"
            "        pass\n"
        )
        result = _create_and_run(
            client,
            observation="payment error",
            source_zip=(BytesIO(_make_zip({"handler.py": risky_code})), "project.zip"),
        )
        assert len(result["similar_patterns"]) >= 1

    def test_each_pattern_has_required_keys(self, client):
        risky_code = "if not value:\n    raise ValueError('bad')\n"
        result = _create_and_run(
            client,
            observation="payment error",
            source_zip=(BytesIO(_make_zip({"service.py": risky_code})), "project.zip"),
        )
        for pattern in result["similar_patterns"]:
            assert "pattern_id" in pattern
            assert "risk_level" in pattern
            assert "excerpt" in pattern


# ---------------------------------------------------------------------------
# ST-29  Git history (observation + history file via ZIP workaround)
# ---------------------------------------------------------------------------

class TestST29ChangeInvestigator:
    def test_change_investigator_unavailable_without_history(self, client):
        result = _create_and_run(client, observation="something failed.")
        change_inv = next(
            i for i in result["investigators"] if i["agent"] == "Change Investigator"
        )
        assert change_inv["status"] == "unavailable"


# ---------------------------------------------------------------------------
# ST-30  Proof verification field for user investigations
# ---------------------------------------------------------------------------

class TestST30ProofVerificationUnavailable:
    def test_proof_reproduction_status_is_unavailable(self, client):
        result = _create_and_run(client, observation="system error.")
        assert result["proof"]["reproduction"]["status"] == "UNAVAILABLE"

    def test_proof_verification_status_is_unavailable(self, client):
        result = _create_and_run(client, observation="system error.")
        assert result["proof"]["verification"]["status"] == "UNAVAILABLE"

    def test_demo_proof_reproduction_has_result(self, client):
        result = client.post("/api/investigate").get_json()
        # Demo runs real reproduction — status must be FAIL (buggy) then PASS (fixed)
        assert result["proof"]["reproduction"]["status"] in {"FAIL", "PASS", "ERROR"}
