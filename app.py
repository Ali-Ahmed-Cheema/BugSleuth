"""BugSleuth Flask application entry point.

This module wires together the investigation APIs and the web UI. It keeps the
application startup simple so a normal user can run the project with a single
command while preserving the existing investigation workflow.
"""

from pathlib import Path
import json

from flask import Flask, jsonify, render_template, request
from uuid import uuid4

from services.file_service import create_investigation_dir, save_log, save_project_zip
from services.github_service import save_github_repository
from services.investigation_service import run_investigation
from verification.trusted_demo import run_trusted_demo_verification


ROOT = Path(__file__).parent
DATA = ROOT / "incident_data"

# Flask app configuration: keep the local-only prototype easy to run and simple to
# understand for a user working on a laptop or dev machine.
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 22 * 1024 * 1024
app.secret_key = "bugsleuth-local-prototype"

UPLOAD_ROOT = ROOT / "uploads"
UPLOAD_ROOT.mkdir(exist_ok=True)

INVESTIGATIONS = {}
app.INVESTIGATIONS = INVESTIGATIONS


def load_incident() -> dict:
    return json.loads((DATA / "incident.json").read_text(encoding="utf-8"))


def demo_package() -> dict:
    incident = load_incident()
    return {"investigation_id": "DEMO-INC-2026-001", "incident": incident, "logs_path": DATA / "application.log", "source_path": ROOT / "sample_app" / "payment_service.py", "history_path": DATA / "git_history.txt"}


def new_incident(observation: str, logs_filename: str | None, source_filename: str | None, path, github_repository: dict | None = None, github_url: str | None = None) -> dict:
    source_path = str(path / "source") if source_filename else (github_repository["source_path"] if github_repository else None)
    history_path = github_repository["history_path"] if github_repository else None
    evidence = {
        "logs": {"provided": bool(logs_filename), "source": "uploaded" if logs_filename else None},
        "source_code": {
            "type": "github" if github_repository else ("zip" if source_filename else "none"),
            "repository": github_repository["repository"] if github_repository else None,
            "default_branch": github_repository.get("default_branch") if github_repository else None,
            "provided": bool(source_filename or github_repository),
        },
        "git_history": {"provided": bool(history_path), "source": "GitHub" if github_repository else None},
    }
    return {
        "investigation_id": f"INV-{uuid4().hex[:8].upper()}",
        "incident": {"incident_id": "user-supplied", "service": "Unknown service", "title": "User-submitted incident", "severity": "UNTRIAGED", "deployment_version": "Unknown", "incident_start": "Unknown", "user_impact": observation or "Not provided", "error_summary": "Not yet determined", "description": observation or "No observation supplied."},
        "user_observation": observation,
        "logs_filename": logs_filename,
        "source_filename": source_filename,
        "github_repository": github_repository,
        "github_url": github_url,
        "logs_path": str(path / logs_filename) if logs_filename else None,
        "source_path": source_path,
        "history_path": history_path,
        "evidence": evidence,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/investigate")
def investigate_api():
    return jsonify(run_investigation(demo_package(), demo=True))


@app.post("/api/investigations")
def create_investigation():
    observation = request.form.get("observation", "").strip()
    log_upload = request.files.get("logs")
    source_upload = request.files.get("source_zip")
    github_repo_url = (request.form.get("github_repo_url") or "").strip()

    # Check if at least one piece of evidence is provided
    if not observation and not (log_upload and log_upload.filename) and not (source_upload and source_upload.filename) and not github_repo_url:
        return jsonify({"error": "No evidence was provided. Upload logs, source code, connect a GitHub repository, or add an observation to begin."}), 400

    # Validate file sizes (max 20 MB)
    MAX_FILE_SIZE = 20 * 1024 * 1024

    if log_upload and log_upload.filename:
        log_upload.seek(0, 2)  # Seek to end
        log_size = log_upload.tell()
        log_upload.seek(0)  # Reset to beginning
        if log_size > MAX_FILE_SIZE:
            return jsonify({"error": f"Log file exceeds maximum allowed size of 20 MB."}), 400

    if source_upload and source_upload.filename:
        source_upload.seek(0, 2)  # Seek to end
        source_size = source_upload.tell()
        source_upload.seek(0)  # Reset to beginning
        if source_size > MAX_FILE_SIZE:
            return jsonify({"error": f"Source ZIP file exceeds maximum allowed size of 20 MB."}), 400

    try:
        path = create_investigation_dir(UPLOAD_ROOT)
        logs_filename = save_log(log_upload, path) if log_upload and log_upload.filename else None
        source_filename = save_project_zip(source_upload, path) if source_upload and source_upload.filename else None
        github_repository = save_github_repository(github_repo_url, path) if github_repo_url else None
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    package = new_incident(observation, logs_filename, source_filename, path, github_repository=github_repository, github_url=github_repo_url)
    INVESTIGATIONS[package["investigation_id"]] = package
    return jsonify({"investigation_id": package["investigation_id"], "status": "created"}), 201


@app.post("/api/investigations/<investigation_id>/run")
def run_user_investigation(investigation_id: str):
    package = INVESTIGATIONS.get(investigation_id)
    if not package:
        return jsonify({"error": "Investigation could not be found."}), 404
    try:
        result = run_investigation(package)
    except OSError:
        return jsonify({"error": "Investigation could not be completed. Please review the evidence and try again."}), 500
    return jsonify(result)


@app.post("/api/investigations/<investigation_id>/verify")
def verify_investigation(investigation_id: str):
    """Execute verification only for BugSleuth's bundled, trusted demo."""
    if investigation_id != "DEMO-INC-2026-001":
        return jsonify({
            "status": "unavailable",
            "execution_policy": "untrusted_code_not_executed",
            "message": "For safety, BugSleuth does not execute uploaded or GitHub repository code. Run verification in your own isolated environment.",
        }), 403
    return jsonify(run_trusted_demo_verification())


@app.get("/investigations/<investigation_id>")
def investigation_page(investigation_id: str):
    if investigation_id not in INVESTIGATIONS and investigation_id != "DEMO-INC-2026-001":
        return render_template("index.html"), 404
    return render_template("index.html", investigation_id=investigation_id)


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/help")
def help():
    return render_template("help.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
