# BugSleuth

> **IBM TechXchange 2026 Pre-conference Dev Day Hackathon — Team BobBuilders**

BugSleuth is a local-first, evidence-driven software incident investigation web application. When a service crashes, a payment fails, or an API starts returning errors, BugSleuth helps engineers understand *why* — by analyzing real evidence instead of guessing.

It accepts application logs, source code ZIP files, public GitHub repository URLs, and plain-text observations, then produces a structured investigation report backed by cited facts, adversarial review, and an explicit confidence verdict.

**Zero cloud dependencies. Zero AI API keys. One command to run.**

---

## Quick Start

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the application
python run.py
```

Then open **http://127.0.0.1:5000/** in your browser.

---

## What Problem Does It Solve?

When production incidents happen, the typical investigation looks like this:
- Engineers frantically scan logs manually
- Someone reads a stack trace and starts guessing
- Hypotheses are formed without evidence
- Fixes are deployed without proof the fix addresses the root cause

BugSleuth replaces that chaos with a **disciplined, evidence-first workflow**:

1. Collect all available evidence
2. Identify what the evidence actually proves (catalogued as labelled facts)
3. Form and evaluate hypotheses against those facts
4. Put those hypotheses through adversarial tribunal review
5. Issue a verdict only when the evidence supports it
6. Honestly report `MORE_EVIDENCE_NEEDED` when it doesn't

---

## How It Works

### Evidence You Can Submit

| Type | Description |
|---|---|
| Application Logs | `.log` or `.txt` file from a running system |
| Source Code ZIP | Compressed archive of the failing project |
| GitHub Repository URL | Any public repo — cloned via the GitHub API |
| Free-Text Observation | A short description of what went wrong |

### The Investigation Pipeline

```
Evidence → 5 Investigators → Evidence Catalog (E-NNN IDs)
        → Tribunal (Prosecutor → Defense → Judge)
        → Trust Layer + Schema Validation
        → Timeline + Pattern Detection + Project Profile
        → Dashboard Report
```

**Five investigators** analyze the evidence: Log, Code, Change, Pipeline, and Deployment Context.  
**Three tribunal agents** then debate it: Prosecutor builds the case, Defense challenges it, Judge issues the verdict.

### Verdicts

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | Evidence converges on a single cause |
| `MOST_LIKELY` | Strong evidence, no reproduction yet |
| `MORE_EVIDENCE_NEEDED` | Multiple hypotheses remain plausible |
| `REJECTED` | Leading hypothesis is contradicted by evidence |

---

## Key Features

- **Evidence-cited conclusions** — every claim references an `E-NNN` fact ID
- **Adversarial tribunal** — a Prosecutor, Defense, and Judge review every investigation
- **Five specialist investigators** — Log, Code (static only), Change, Pipeline, Deployment
- **Auto project detection** — language, framework, entry points, CI/CD, Docker/K8s
- **Incident timeline** — chronological view of errors, deployments, and code changes
- **Pattern detection** — finds risky code patterns similar to the root cause
- **Trust layer validation** — every response is validated against a JSON Schema contract
- **RED → GREEN demo proof** — live test reproduction for the bundled demo scenario
- **No untrusted code execution** — user-uploaded code is analyzed statically only

---

## The Demo Scenario

BugSleuth ships with a built-in demonstration around a real, intentional Python bug:

```python
# The buggy payment service
def process_payment(payment_amount: float) -> str:
    if not payment_amount:          # BUG: falsy check rejects valid zero-value payments
        raise ValueError("Invalid payment amount")
    return "Payment processed"
```

A payment of `0` (zero) is valid in a promotional flow — but `if not 0` evaluates to `True` in Python, so the function incorrectly rejects it. The demo traces this through logs and git history, runs a failing RED test, applies the fix, and verifies a passing GREEN test — all on a temporary copy. The original is never modified.

Click **"Run Demo Investigation"** on the home page to see it end-to-end.

---

## Project Structure

```
BugSleuth/
├── app.py                          # Flask app, API routes
├── run.py                          # One-command startup script
├── requirements.txt
├── pytest.ini
│
├── investigators/                  # Five investigation agents
│   ├── base.py
│   ├── log_investigator.py
│   ├── code_investigator.py
│   ├── change_investigator.py
│   ├── pipeline_investigator.py
│   └── deployment_context_investigator.py
│
├── tribunal/                       # Adversarial reasoning system
│   ├── prosecutor.py
│   ├── defense.py
│   └── judge.py
│
├── services/                       # Core analysis and orchestration
│   ├── investigation_service.py
│   ├── project_analyzer.py
│   ├── timeline_builder.py
│   ├── pattern_detector.py
│   ├── evidence_catalog.py
│   ├── trust_schema.py
│   ├── investigation_summary.py
│   ├── file_service.py
│   └── github_service.py
│
├── models/                         # Domain data models
├── utils/                          # Shared helpers
├── verification/                   # RED → GREEN proof engine (demo only)
├── templates/                      # HTML pages
├── static/                         # CSS and JavaScript assets
├── sample_app/                     # Bundled demo application
├── incident_data/                  # Demo incident payloads
├── tests/                          # Unit, integration, and API tests
└── bob-session-screenshots/        # IBM Bob task session summaries (hackathon requirement)
```

---

## Running the Tests

```powershell
pytest -q
```

The suite has three layers: unit tests (every model and service), integration tests (pipeline boundaries), and API scenario tests (end-to-end HTTP).

---

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12+, Flask 3.x |
| Frontend | Vanilla HTML5 / CSS3 / JavaScript |
| Testing | Pytest 8.x |
| Schema validation | `jsonschema` (Draft 7) |
| GitHub integration | Python `urllib` (no third-party HTTP library) |
| Storage | Local filesystem, in-memory Flask process |

**No external AI API calls. The entire system is deterministic and runs fully offline.**

---

## IBM Bob Session Screenshots

The [`bob-session-screenshots/`](./bob-session-screenshots/) directory contains exported IBM Bob task session summary screenshots documenting how IBM Bob was used throughout the development of this project, as required by the hackathon submission guidelines.

---

## Safety

| Principle | How It Is Enforced |
|---|---|
| No untrusted code execution | Only the bundled `sample_app/` is ever run, in a temp directory |
| No speculation | Every claim cites an `E-NNN` fact ID |
| Honest about gaps | `MORE_EVIDENCE_NEEDED` when evidence is insufficient |
| File safety | Zip path traversal detection, 20 MB size limit |
| Schema validation | Trust layer validated against JSON Schema on every run |

---

## Built For

**IBM TechXchange 2026 Pre-conference Dev Day Hackathon**  
Team: **BobBuilders**  
Built entirely with IBM Bob as the AI development foundation.
