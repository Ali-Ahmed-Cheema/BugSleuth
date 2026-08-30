"""
User Acceptance Tests (UAT) for BugSleuth.

These tests verify that the software meets the user's stated requirements as
described in the README, IMPLEMENTATION_SUMMARY, and V4_UPGRADE_SUMMARY docs.

Each test class maps to one user-facing requirement or usage scenario.

Requirements covered
────────────────────
UAT-01  A user can start a new investigation with only an observation.
UAT-02  An observation-only investigation returns a conservative verdict.
UAT-03  A user can upload a log file and it is analyzed correctly.
UAT-04  A log file drives timeline event extraction.
UAT-05  A user can upload a source ZIP and the code is inspected.
UAT-06  A user can supply a GitHub URL and evidence is included in the package.
UAT-07  An invalid GitHub URL is rejected with a clear error.
UAT-08  An unsupported file extension is rejected before investigation.
UAT-09  An oversized file upload is rejected before investigation.
UAT-10  A ZIP with path-traversal entries is rejected before investigation.
UAT-11  Every cited evidence item carries a sequential E-NNN id labelled FACT.
UAT-12  The hypothesis in the trust layer cites evidence IDs.
UAT-13  All required dashboard keys are present in the investigation result.
UAT-14  Untrusted code is never executed — verify endpoint returns 403.
UAT-15  The bundled demo investigation runs and is verifiable.
UAT-16  Two concurrent investigations are fully independent.
UAT-17  A UTF-16 encoded log upload is accepted and investigated.
UAT-18  Requesting an unknown investigation ID returns 404.
UAT-19  A user investigation never contains demo-specific data.
UAT-20  The application home page is reachable and returns HTML.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from app import app as flask_app


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip(entries: dict[str, str]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _create_and_run(client, **form_kwargs) -> dict:
    """Create an investigation and immediately run it; return the result JSON."""
    resp = client.post(
        "/api/investigations",
        data=form_kwargs,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, f"create failed: {resp.get_json()}"
    inv_id = resp.get_json()["investigation_id"]
    run_resp = client.post(f"/api/investigations/{inv_id}/run")
    assert run_resp.status_code == 200, f"run failed: {run_resp.get_json()}"
    return run_resp.get_json()


# ============================================================================
# UAT-01  A user can start a new investigation with only an observation
# ============================================================================

class TestUAT01StartWithObservation:
    """UAT-01: Users can initiate an investigation by supplying just a text
    observation — no files required."""

    def test_observation_only_returns_201_and_investigation_id(self, client):
        resp = client.post(
            "/api/investigations",
            data={"observation": "The API is returning 500 errors."},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert "investigation_id" in body
        assert body["investigation_id"].startswith("INV-")
        assert body["status"] == "created"

    def test_empty_submission_is_rejected(self, client):
        resp = client.post("/api/investigations", data={})
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body


# ============================================================================
# UAT-02  Observation-only investigation returns a conservative verdict
# ============================================================================

class TestUAT02ConservativeVerdict:
    """UAT-02: Without logs or source code, the tribunal must not over-commit
    to a verdict — it should return MORE_EVIDENCE_NEEDED."""

    def test_verdict_is_more_evidence_needed(self, client):
        result = _create_and_run(
            client,
            observation="Requests are timing out occasionally.",
        )
        verdict = result["tribunal"]["judge"]["verdict"]
        assert verdict == "MORE_EVIDENCE_NEEDED", (
            f"Expected MORE_EVIDENCE_NEEDED for observation-only, got {verdict!r}"
        )

    def test_missing_evidence_list_mentions_logs(self, client):
        result = _create_and_run(
            client,
            observation="Something is broken in production.",
        )
        missing = result["ledger"]["missing_evidence"]
        assert any("log" in item.lower() for item in missing), (
            "Expected 'logs' to appear in missing_evidence"
        )

    def test_proof_verification_is_unavailable(self, client):
        result = _create_and_run(
            client,
            observation="Random errors in the payment flow.",
        )
        assert result["proof"]["verification"]["status"] == "UNAVAILABLE"


# ============================================================================
# UAT-03  A log file is analyzed and produces evidence
# ============================================================================

class TestUAT03LogFileAnalysis:
    """UAT-03: When the user uploads a log file containing error lines, the
    Log Investigator should complete and produce evidence items."""

    def test_log_investigator_completes(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR database connection refused\n"), "app.log"),
        )
        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert log_inv["status"] == "complete"

    def test_log_evidence_items_are_populated(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR request failed\n"), "incident.log"),
        )
        log_inv = next(i for i in result["investigators"] if i["agent"] == "Log Investigator")
        assert len(log_inv["evidence"]) >= 1
        # Evidence line should reference the uploaded filename
        assert "incident.log" in log_inv["evidence"][0]

    def test_log_only_verdict_is_most_likely(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR request failed\n"), "incident.log"),
        )
        verdict = result["tribunal"]["judge"]["verdict"]
        assert verdict in {"MOST_LIKELY", "CONFIRMED"}, (
            f"Expected MOST_LIKELY or CONFIRMED with clear log evidence, got {verdict!r}"
        )

    def test_trust_layer_has_no_validation_errors(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR db refused\n"), "app.log"),
        )
        assert result["trust_layer"]["validation_errors"] == []


# ============================================================================
# UAT-04  Log file drives timeline event extraction
# ============================================================================

class TestUAT04TimelineFromLog:
    """UAT-04: Log lines with timestamps become timeline events, and the
    investigation timeline is always initialised with an INVESTIGATION-001 event."""

    def test_timeline_includes_investigation_start_event(self, client):
        result = _create_and_run(
            client,
            observation="Something went wrong.",
        )
        event_ids = [e["event_id"] for e in result["timeline"]["events"]]
        assert "INVESTIGATION-001" in event_ids

    def test_error_log_line_creates_error_timeline_event(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR timeout reached\n"), "app.log"),
        )
        event_types = [e["event_type"] for e in result["timeline"]["events"]]
        assert "ERROR" in event_types

    def test_warning_log_line_creates_warning_timeline_event(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T09:00:00 WARN deprecated api used\n"), "app.log"),
        )
        event_types = [e["event_type"] for e in result["timeline"]["events"]]
        assert "WARNING" in event_types

    def test_timeline_dict_has_event_count_field(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"), "app.log"),
        )
        assert "event_count" in result["timeline"]
        assert result["timeline"]["event_count"] >= 1


# ============================================================================
# UAT-05  Source ZIP produces code investigation findings
# ============================================================================

class TestUAT05SourceZipAnalysis:
    """UAT-05: When the user uploads a source ZIP, the Code Investigator should
    complete and identify risky code patterns."""

    def test_code_investigator_completes_for_zip_upload(self, client):
        zip_bytes = _make_zip({
            "service.py": "def pay(amount):\n    if not amount:\n        raise ValueError('bad')\n"
        })
        result = _create_and_run(
            client,
            source_zip=(BytesIO(zip_bytes), "project.zip"),
            observation="payment error",
        )
        code_inv = next(i for i in result["investigators"] if i["agent"] == "Code Investigator")
        assert code_inv["status"] == "complete"

    def test_similar_patterns_detected_for_risky_code(self, client):
        zip_bytes = _make_zip({
            "handler.py": (
                "def handle(x):\n"
                "    if not x:\n"
                "        raise ValueError('bad')\n"
                "    try:\n"
                "        process(x)\n"
                "    except:\n"
                "        pass\n"
            )
        })
        result = _create_and_run(
            client,
            source_zip=(BytesIO(zip_bytes), "project.zip"),
            observation="handler failing",
        )
        assert isinstance(result["similar_patterns"], list)
        assert len(result["similar_patterns"]) >= 1

    def test_clean_source_produces_no_similar_patterns(self, client):
        zip_bytes = _make_zip({
            "utils.py": "def add(a, b):\n    return a + b\n"
        })
        result = _create_and_run(
            client,
            source_zip=(BytesIO(zip_bytes), "utils.zip"),
            observation="addition seems wrong",
        )
        assert result["similar_patterns"] == []


# ============================================================================
# UAT-06  GitHub URL is accepted and evidence is included
# ============================================================================

class TestUAT06GitHubURL:
    """UAT-06: A valid public GitHub URL is accepted; evidence is wired into
    the investigation package."""

    def test_valid_github_url_returns_201(self, client, monkeypatch):
        def fake_save(url, destination):
            repo_dir = destination / "repo"
            repo_dir.mkdir(exist_ok=True)
            (repo_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
            (destination / "git_history.json").write_text(
                '{"commits": [{"sha": "abc1234", "message": "Initial", "timestamp": "2026-01-01T00:00:00Z"}]}',
                encoding="utf-8",
            )
            return {
                "repository": "octocat/Hello-World",
                "default_branch": "main",
                "description": "Test",
                "language": "Python",
                "source_path": str(repo_dir),
                "history_path": str(destination / "git_history.json"),
                "commits": [],
            }

        monkeypatch.setattr("app.save_github_repository", fake_save)
        resp = client.post(
            "/api/investigations",
            data={"github_repo_url": "https://github.com/octocat/Hello-World"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        assert resp.get_json()["investigation_id"].startswith("INV-")

    def test_github_package_has_source_and_history_paths(self, client, monkeypatch):
        def fake_save(url, destination):
            repo_dir = destination / "repo"
            repo_dir.mkdir(exist_ok=True)
            (repo_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
            (destination / "git_history.json").write_text(
                '{"commits": []}', encoding="utf-8"
            )
            return {
                "repository": "demo/repo",
                "default_branch": "main",
                "description": "",
                "language": "Python",
                "source_path": str(repo_dir),
                "history_path": str(destination / "git_history.json"),
                "commits": [],
            }

        monkeypatch.setattr("app.save_github_repository", fake_save)
        resp = client.post(
            "/api/investigations",
            data={"github_repo_url": "https://github.com/demo/repo"},
            content_type="multipart/form-data",
        )
        from app import INVESTIGATIONS
        pkg = INVESTIGATIONS[resp.get_json()["investigation_id"]]
        assert pkg["source_path"] is not None
        assert pkg["history_path"] is not None
        assert pkg["github_repository"]["repository"] == "demo/repo"


# ============================================================================
# UAT-07  Invalid GitHub URL is rejected with a clear error
# ============================================================================

class TestUAT07InvalidGitHubURL:
    """UAT-07: Submitting a URL that is not a public GitHub repository must
    return HTTP 400 with a descriptive error message."""

    def test_non_github_url_returns_400(self, client):
        resp = client.post(
            "/api/investigations",
            data={"github_repo_url": "https://example.com/not-github"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body
        assert "github" in body["error"].lower()

    def test_plaintext_string_as_url_returns_400(self, client):
        resp = client.post(
            "/api/investigations",
            data={"github_repo_url": "not-a-url-at-all"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ============================================================================
# UAT-08  Unsupported file extension is rejected
# ============================================================================

class TestUAT08BadFileExtension:
    """UAT-08: Uploading a file with an unsupported extension must be rejected
    before any investigation is run."""

    def test_csv_log_file_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(b"col1,col2\nerror,crash\n"), "logs.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_non_zip_source_file_rejected(self, client):
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (BytesIO(b"binary data"), "project.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ============================================================================
# UAT-09  Oversized file upload is rejected
# ============================================================================

class TestUAT09OversizedFile:
    """UAT-09: Files exceeding the 20 MB limit must be rejected before any
    investigation is attempted."""

    def test_oversized_log_file_returns_400(self, client):
        big_data = b"x" * (21 * 1024 * 1024)  # 21 MB
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(big_data), "huge.log")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "error" in body


# ============================================================================
# UAT-10  Path-traversal ZIP is rejected
# ============================================================================

class TestUAT10PathTraversalZip:
    """UAT-10: A ZIP containing path-traversal entries (e.g. ../../evil.py)
    must be rejected — uploaded code must never be placed outside the upload
    directory."""

    def test_path_traversal_zip_returns_400(self, client):
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../outside.py", "print('evil')")
        buf.seek(0)
        resp = client.post(
            "/api/investigations",
            data={"source_zip": (buf, "attack.zip")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400


# ============================================================================
# UAT-11  Every evidence item carries a sequential E-NNN id labelled FACT
# ============================================================================

class TestUAT11EvidenceIDs:
    """UAT-11: The README states 'Every directly cited item is assigned an
    E-NNN evidence ID and labelled as a fact.'"""

    def test_facts_have_sequential_e_nnn_ids(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR db refused\n"), "app.log"),
        )
        facts = result["trust_layer"]["facts"]
        assert len(facts) >= 1
        for i, fact in enumerate(facts, start=1):
            assert fact["id"] == f"E-{i:03d}", (
                f"Expected E-{i:03d}, got {fact['id']!r}"
            )

    def test_all_facts_are_labelled_as_fact(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"), "app.log"),
        )
        facts = result["trust_layer"]["facts"]
        assert all(f["attribution"] == "FACT" for f in facts)


# ============================================================================
# UAT-12  The hypothesis in the trust layer cites evidence IDs
# ============================================================================

class TestUAT12HypothesisCitesEvidence:
    """UAT-12: The README states 'Hypotheses and tribunal arguments cite those
    IDs'. The trust layer hypothesis must reference at least one E-NNN id."""

    def test_hypothesis_evidence_ids_are_not_empty(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR crash\n"), "app.log"),
        )
        hyp = result["trust_layer"]["hypothesis"]
        assert len(hyp["evidence_ids"]) >= 1

    def test_hypothesis_evidence_ids_match_facts(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR db refused\n"), "app.log"),
        )
        fact_ids = {f["id"] for f in result["trust_layer"]["facts"]}
        hyp_ids = set(result["trust_layer"]["hypothesis"]["evidence_ids"])
        assert hyp_ids.issubset(fact_ids), (
            f"Hypothesis cited {hyp_ids - fact_ids} which are not in facts"
        )


# ============================================================================
# UAT-13  All required dashboard keys are present in the investigation result
# ============================================================================

class TestUAT13RequiredDashboardKeys:
    """UAT-13: The investigation result JSON must contain all keys required to
    render the dashboard (README 'How the app works' section)."""

    REQUIRED_KEYS = {
        "incident",
        "investigation_id",
        "mode",
        "trust_layer",
        "tribunal",
        "investigators",
        "ledger",
        "proof",
        "timeline",
        "similar_patterns",
        "investigation_summary",
        "evidence_strength",
        "recommended_actions",
        "investigator_timeline",
        "project_discovery",
    }

    def test_observation_only_result_has_all_dashboard_keys(self, client):
        result = _create_and_run(client, observation="Something broke.")
        missing = self.REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing dashboard keys: {missing}"

    def test_log_only_result_has_all_dashboard_keys(self, client):
        result = _create_and_run(
            client,
            logs=(BytesIO(b"2026-08-29T10:00:00Z ERROR db refused\n"), "app.log"),
        )
        missing = self.REQUIRED_KEYS - result.keys()
        assert not missing, f"Missing dashboard keys: {missing}"

    def test_tribunal_has_prosecutor_defense_judge(self, client):
        result = _create_and_run(client, observation="Something broke.")
        tribunal = result["tribunal"]
        assert "prosecutor" in tribunal
        assert "defense" in tribunal
        assert "judge" in tribunal

    def test_verdict_is_one_of_the_four_allowed_values(self, client):
        result = _create_and_run(client, observation="Something broke.")
        verdict = result["tribunal"]["judge"]["verdict"]
        assert verdict in {"CONFIRMED", "MOST_LIKELY", "MORE_EVIDENCE_NEEDED", "REJECTED"}


# ============================================================================
# UAT-14  Untrusted code is never executed
# ============================================================================

class TestUAT14UntrustedCodeNotExecuted:
    """UAT-14: The README states 'untrusted uploaded code is never executed'.
    The /verify endpoint must return 403 for any non-demo investigation ID."""

    def test_verify_returns_403_for_user_investigation(self, client):
        create_resp = client.post(
            "/api/investigations",
            data={"observation": "Some error."},
            content_type="multipart/form-data",
        )
        inv_id = create_resp.get_json()["investigation_id"]
        resp = client.post(f"/api/investigations/{inv_id}/verify")
        assert resp.status_code == 403

    def test_verify_403_body_states_execution_policy(self, client):
        create_resp = client.post(
            "/api/investigations",
            data={"observation": "Some error."},
            content_type="multipart/form-data",
        )
        inv_id = create_resp.get_json()["investigation_id"]
        body = client.post(f"/api/investigations/{inv_id}/verify").get_json()
        assert body["execution_policy"] == "untrusted_code_not_executed"

    def test_verify_403_for_arbitrary_fake_id(self, client):
        resp = client.post("/api/investigations/FAKE-ID-9999/verify")
        assert resp.status_code == 403


# ============================================================================
# UAT-15  The bundled demo investigation runs and is verifiable
# ============================================================================

class TestUAT15DemoInvestigation:
    """UAT-15: The built-in demo investigation must run successfully and the
    /verify endpoint must return 200 for DEMO-INC-2026-001."""

    def test_demo_investigate_endpoint_returns_200(self, client):
        resp = client.post("/api/investigate")
        assert resp.status_code == 200

    def test_demo_result_has_no_trust_layer_validation_errors(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["trust_layer"]["validation_errors"] == []

    def test_demo_verify_endpoint_returns_200(self, client):
        resp = client.post("/api/investigations/DEMO-INC-2026-001/verify")
        assert resp.status_code == 200

    def test_demo_trust_layer_has_facts_and_hypothesis(self, client):
        result = client.post("/api/investigate").get_json()
        assert result["trust_layer"]["facts"]
        assert result["trust_layer"]["hypothesis"]["evidence_ids"]


# ============================================================================
# UAT-16  Two investigations are fully independent
# ============================================================================

class TestUAT16MultipleInvestigations:
    """UAT-16: Running two investigations must not cross-contaminate results —
    each gets its own ID and its own evidence set."""

    def test_two_observations_produce_different_ids(self, client):
        r1 = client.post(
            "/api/investigations",
            data={"observation": "First issue."},
            content_type="multipart/form-data",
        )
        r2 = client.post(
            "/api/investigations",
            data={"observation": "Second issue."},
            content_type="multipart/form-data",
        )
        id1 = r1.get_json()["investigation_id"]
        id2 = r2.get_json()["investigation_id"]
        assert id1 != id2

    def test_second_investigation_does_not_inherit_first_log(self, client):
        # First investigation has a log with a specific error
        r1 = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(b"2026-08-29T10:00:00Z ERROR specific-error-alpha\n"), "app.log")},
            content_type="multipart/form-data",
        )
        id1 = r1.get_json()["investigation_id"]

        # Second investigation has no log
        r2 = client.post(
            "/api/investigations",
            data={"observation": "A different unrelated issue."},
            content_type="multipart/form-data",
        )
        id2 = r2.get_json()["investigation_id"]

        result2 = client.post(f"/api/investigations/{id2}/run").get_json()
        # Second result must not contain the first investigation's error token
        assert "specific-error-alpha" not in str(result2)


# ============================================================================
# UAT-17  UTF-16 encoded log upload is accepted
# ============================================================================

class TestUAT17Utf16LogUpload:
    """UAT-17: Log files saved with UTF-16 encoding must be accepted and
    investigated without crashing the application."""

    def test_utf16_log_returns_200_on_run(self, client):
        utf16_bytes = "2026-08-29T10:00:00Z ERROR request failed\n".encode("utf-16")
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(utf16_bytes), "incident.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        inv_id = resp.get_json()["investigation_id"]
        run_resp = client.post(f"/api/investigations/{inv_id}/run")
        assert run_resp.status_code == 200

    def test_utf16_log_investigator_reaches_complete_status(self, client):
        utf16_bytes = "2026-08-29T10:00:00Z ERROR request failed\n".encode("utf-16")
        resp = client.post(
            "/api/investigations",
            data={"logs": (BytesIO(utf16_bytes), "incident.txt")},
            content_type="multipart/form-data",
        )
        inv_id = resp.get_json()["investigation_id"]
        result = client.post(f"/api/investigations/{inv_id}/run").get_json()
        log_inv = result["investigators"][0]
        assert log_inv["status"] == "complete"


# ============================================================================
# UAT-18  Unknown investigation ID returns 404
# ============================================================================

class TestUAT18UnknownInvestigationID:
    """UAT-18: Requesting a run for an ID that does not exist must return
    HTTP 404 with an error message."""

    def test_run_unknown_id_returns_404(self, client):
        resp = client.post("/api/investigations/DOES-NOT-EXIST/run")
        assert resp.status_code == 404

    def test_404_body_has_error_key(self, client):
        body = client.post("/api/investigations/DOES-NOT-EXIST/run").get_json()
        assert "error" in body


# ============================================================================
# UAT-19  A user investigation never contains demo-specific data
# ============================================================================

class TestUAT19NoDataLeakFromDemo:
    """UAT-19: Running a user investigation must not leak tokens from the
    bundled demo (payment_amount, abc1234, DEMO-INC-2026-001)."""

    def test_user_run_does_not_contain_demo_tokens(self, client):
        result = _create_and_run(
            client,
            observation="The backend API is returning errors.",
        )
        serialised = str(result)
        assert "payment_amount" not in serialised
        assert "abc1234" not in serialised
        assert "DEMO-INC-2026-001" not in serialised

    def test_user_mode_is_user_not_demo(self, client):
        result = _create_and_run(client, observation="Something broke.")
        assert result["mode"] == "user"


# ============================================================================
# UAT-20  The application home page is reachable
# ============================================================================

class TestUAT20HomePageReachable:
    """UAT-20: The application landing page must be reachable and return
    a valid HTML response."""

    def test_home_page_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_home_page_content_type_is_html(self, client):
        resp = client.get("/")
        assert "text/html" in resp.content_type

    def test_home_page_body_contains_app_name(self, client):
        resp = client.get("/")
        body = resp.data.decode("utf-8", errors="replace")
        assert "BugSleuth" in body
