from io import BytesIO
import zipfile

from app import app


def test_observation_only_investigation_is_conservative():
    client = app.test_client()
    response = client.post("/api/investigations", data={"observation": "Users report slow requests."})
    assert response.status_code == 201
    investigation_id = response.get_json()["investigation_id"]

    result = client.post(f"/api/investigations/{investigation_id}/run").get_json()

    assert result["tribunal"]["judge"]["verdict"] == "MORE_EVIDENCE_NEEDED"
    assert result["proof"]["verification"]["status"] == "UNAVAILABLE"
    assert any("logs" in item.lower() for item in result["ledger"]["missing_evidence"])


def test_log_only_investigation_uses_supplied_lines():
    client = app.test_client()
    response = client.post(
        "/api/investigations",
        data={"logs": (BytesIO(b"2026-08-29T10:00:00Z ERROR request failed\n"), "incident.log")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    investigation_id = response.get_json()["investigation_id"]

    result = client.post(f"/api/investigations/{investigation_id}/run").get_json()

    log_result = next(item for item in result["investigators"] if item["agent"] == "Log Investigator")
    assert log_result["status"] == "complete"
    assert "incident.log:1" in log_result["evidence"][0]
    assert result["tribunal"]["judge"]["verdict"] == "MOST_LIKELY"


def test_utf16_log_upload_is_investigated():
    client = app.test_client()
    response = client.post(
        "/api/investigations",
        data={"logs": (BytesIO("2026-08-29T10:00:00Z ERROR request failed\n".encode("utf-16")), "incident.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    investigation_id = response.get_json()["investigation_id"]

    result = client.post(f"/api/investigations/{investigation_id}/run")

    assert result.status_code == 200
    assert result.get_json()["investigators"][0]["status"] == "complete"


def test_invalid_type_and_unsafe_zip_are_rejected():
    client = app.test_client()
    invalid = client.post(
        "/api/investigations",
        data={"source_zip": (BytesIO(b"not a zip"), "project.txt")},
        content_type="multipart/form-data",
    )
    assert invalid.status_code == 400

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../../outside.py", "print('never execute')")
    archive.seek(0)
    unsafe = client.post(
        "/api/investigations",
        data={"source_zip": (archive, "project.zip")},
        content_type="multipart/form-data",
    )
    assert unsafe.status_code == 400


def test_valid_public_github_repository_url_is_accepted(monkeypatch):
    client = app.test_client()

    def fake_save_repo(url, destination):
        return {
            "repository": "octocat/Hello-World",
            "default_branch": "main",
            "description": "Example repo",
            "language": "Python",
            "source_path": str(destination / "repo"),
            "history_path": str(destination / "git_history.json"),
            "commits": [{"sha": "abc123", "message": "Fix validation", "timestamp": "2026-01-01T00:00:00Z"}],
        }

    monkeypatch.setattr("app.save_github_repository", fake_save_repo)

    response = client.post(
        "/api/investigations",
        data={"github_repo_url": "https://github.com/octocat/Hello-World"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json()["investigation_id"].startswith("INV-")


def test_invalid_github_url_is_rejected():
    client = app.test_client()
    response = client.post(
        "/api/investigations",
        data={"github_repo_url": "https://example.com/not-a-github-repo"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "publicly accessible github repository" in response.get_json()["error"].lower()


def test_git_repo_evidence_is_included_in_package(monkeypatch):
    client = app.test_client()

    def fake_save_repo(url, destination):
        repo_dir = destination / "repo"
        repo_dir.mkdir(exist_ok=True)
        (repo_dir / "payment_service.py").write_text("if not payment_amount:\n    raise ValueError('Invalid payment amount')\n", encoding="utf-8")
        (destination / "git_history.json").write_text(
            '{"commits": [{"sha": "abc1234", "message": "Fix validation", "timestamp": "2026-01-01T00:00:00Z"}]}',
            encoding="utf-8",
        )
        return {
            "repository": "demo/repo",
            "default_branch": "main",
            "description": "Demo repo",
            "language": "Python",
            "source_path": str(repo_dir),
            "history_path": str(destination / "git_history.json"),
            "commits": [{"sha": "abc1234", "message": "Fix validation", "timestamp": "2026-01-01T00:00:00Z"}],
        }

    monkeypatch.setattr("app.save_github_repository", fake_save_repo)

    response = client.post(
        "/api/investigations",
        data={"github_repo_url": "https://github.com/demo/repo"},
        content_type="multipart/form-data",
    )
    package = app.INVESTIGATIONS[response.get_json()["investigation_id"]]

    assert package["github_repository"]["repository"] == "demo/repo"
    assert package["source_path"] is not None
    assert package["history_path"] is not None


def test_github_repo_only_investigation_runs_conservatively(monkeypatch):
    client = app.test_client()

    def fake_save_repo(url, destination):
        repo_dir = destination / "repo"
        repo_dir.mkdir(exist_ok=True)
        (repo_dir / "payment_service.py").write_text("if not payment_amount:\n    raise ValueError('Invalid payment amount')\n", encoding="utf-8")
        (destination / "git_history.json").write_text(
            '{"commits": [{"sha": "abc1234", "message": "Fix validation", "timestamp": "2026-01-01T00:00:00Z"}]}',
            encoding="utf-8",
        )
        return {
            "repository": "demo/repo",
            "default_branch": "main",
            "description": "Demo repo",
            "language": "Python",
            "source_path": str(repo_dir),
            "history_path": str(destination / "git_history.json"),
            "commits": [{"sha": "abc1234", "message": "Fix validation", "timestamp": "2026-01-01T00:00:00Z"}],
        }

    monkeypatch.setattr("app.save_github_repository", fake_save_repo)

    response = client.post(
        "/api/investigations",
        data={"github_repo_url": "https://github.com/demo/repo"},
        content_type="multipart/form-data",
    )
    investigation_id = response.get_json()["investigation_id"]
    result = client.post(f"/api/investigations/{investigation_id}/run").get_json()

    assert result["incident"]["service"] == "Unknown service"
    assert result["mode"] == "user"
    assert result["tribunal"]["judge"]["verdict"] in {"MOST_LIKELY", "MORE_EVIDENCE_NEEDED"}
    assert result["investigators"][1]["agent"] == "Code Investigator"


def test_user_investigation_never_uses_demo_data():
    client = app.test_client()
    response = client.post(
        "/api/investigations",
        data={"observation": "The API is failing in a backend service."},
        content_type="multipart/form-data",
    )
    investigation_id = response.get_json()["investigation_id"]
    result = client.post(f"/api/investigations/{investigation_id}/run").get_json()

    assert result["mode"] == "user"
    assert "payment" not in str(result).lower()
    assert "abc1234" not in str(result).lower()
    assert result["tribunal"]["judge"]["verdict"] in {"MOST_LIKELY", "MORE_EVIDENCE_NEEDED"}


def test_trust_layer_has_auditable_facts_and_valid_contract():
    client = app.test_client()
    result = client.post("/api/investigate").get_json()

    trust_layer = result["trust_layer"]
    assert trust_layer["validation_errors"] == []
    assert trust_layer["facts"]
    assert all(fact["id"].startswith("E-") for fact in trust_layer["facts"])
    assert trust_layer["hypothesis"]["evidence_ids"]


def test_user_code_verification_is_explicitly_unavailable():
    client = app.test_client()
    response = client.post("/api/investigations/not-a-demo/verify")
    assert response.status_code == 403
    assert response.get_json()["execution_policy"] == "untrusted_code_not_executed"


def test_pipeline_investigator_detects_github_actions_and_test_steps(tmp_path):
    from investigators import PipelineInvestigator

    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "ci.yml").write_text(
        "name: CI\n"\
        "on: [push]\n"\
        "jobs:\n"\
        "  test:\n"\
        "    steps:\n"\
        "      - run: pytest tests/\n"\
        "      - run: echo deploy\n",
        encoding="utf-8",
    )

    result = PipelineInvestigator(tmp_path).investigate({})
    assert result["status"] == "complete"
    assert any("GitHub Actions" in item for item in result["findings"]) or any("ci.yml" in item for item in result["evidence"]) or result["pipeline_detected"] is True


def test_deployment_context_investigator_detects_docker_and_kubernetes(tmp_path):
    from investigators import DeploymentContextInvestigator

    (tmp_path / "Dockerfile").write_text("FROM python:3.12\nCOPY . /app\nEXPOSE 8000\nCMD [\"python\", \"app.py\"]\n", encoding="utf-8")
    k8s_dir = tmp_path / "k8s"
    k8s_dir.mkdir()
    (k8s_dir / "deployment.yaml").write_text(
        "apiVersion: apps/v1\n"\
        "kind: Deployment\n"\
        "metadata:\n"\
        "  name: web\n"\
        "spec:\n"\
        "  replicas: 3\n",
        encoding="utf-8",
    )

    result = DeploymentContextInvestigator(tmp_path).investigate({})
    assert result["status"] == "complete"
    assert result["deployment_profile"]["containerization"] in {"Docker detected", "Dockerfile detected"}
    assert result["deployment_profile"]["orchestration"] in {"Kubernetes detected", "Kubernetes manifests detected"}
    assert "replica" in " ".join(result["findings"]).lower()


def test_project_without_devops_files_is_handled_gracefully(tmp_path):
    from investigators import PipelineInvestigator, DeploymentContextInvestigator

    pipeline = PipelineInvestigator(tmp_path).investigate({})
    deployment = DeploymentContextInvestigator(tmp_path).investigate({})

    assert pipeline["pipeline_detected"] is False
    assert deployment["deployment_profile"]["containerization"] == "Not detected"
    assert deployment["deployment_profile"]["orchestration"] == "Not detected"
