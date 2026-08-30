# BugSleuth — About This Project

---

## What Is BugSleuth?

**BugSleuth** is a local-first, evidence-driven software incident investigation web application. It was built specifically for the **IBM TechXchange 2026** hackathon. The core idea is simple but powerful: when a software system fails — a service crashes, a payment goes wrong, an API starts returning 500 errors — developers and engineers need to understand *why* it happened. Most tools give you raw data and leave you guessing. BugSleuth does the opposite. It takes your raw evidence — logs, source code, git history, GitHub links, or even just a plain-text observation — and produces a **structured investigation report** backed by real facts, not hallucination or speculation.

BugSleuth is intentionally **local-only**. It runs on your laptop with a single command. It requires no cloud account, no paid API key, no external AI service, no database setup. Everything is self-contained. You give it evidence, it gives you a verdict.

---

## What Problem Does It Solve?

When production incidents happen, the typical investigation looks like this:
- Engineers frantically scan logs manually
- Someone reads a stack trace and starts guessing
- Hypotheses are formed without evidence
- Fixes are deployed without proof the fix actually addresses the root cause

BugSleuth replaces that chaos with a **disciplined, evidence-first workflow**:
1. Collect all available evidence
2. Identify what the evidence actually proves (facts)
3. Form and evaluate hypotheses against those facts
4. Put those hypotheses through adversarial review (a "tribunal")
5. Only issue a verdict when the evidence supports it
6. Tell you honestly when the evidence is insufficient

It never invents a root cause. If the evidence doesn't support a strong conclusion, the system says **"MORE_EVIDENCE_NEEDED"** and tells you exactly what to go collect.

---

## Who Is This For?

- **Software engineers** debugging production failures
- **DevOps / SRE teams** doing post-mortems and incident reviews
- **QA engineers** investigating recurring bugs
- **Hackathon evaluators** looking at a fully working, thoughtfully engineered project
- **Anyone** who has ever looked at a wall of logs and thought: *"I wish something would just tell me what's wrong"*

---

## How Does the Application Work?

### 1. The User Submits Evidence

The user visits the web app at `http://127.0.0.1:5000/` and provides one or more of the following:

| Evidence Type | Description |
|---|---|
| **Application Logs** | A `.log` or `.txt` file from a running system |
| **Source Code ZIP** | A compressed archive of the failing project |
| **GitHub Repository URL** | A public GitHub repo URL (cloned automatically) |
| **Free-Text Observation** | A short description of what went wrong |

At least one piece of evidence must be provided. The app validates file size (max 20 MB), checks for unsafe zip paths (path traversal attacks), and validates GitHub URLs before accepting anything.

### 2. An Investigation Package Is Created

Once evidence is accepted, a unique investigation package is assembled:
- A unique **Investigation ID** (e.g. `INV-3A8F1C2B`) is assigned
- Uploaded files are saved to a private local directory under `uploads/`
- A GitHub repo is cloned file-by-file via the GitHub API (up to 200 files) without ever executing the repository's code
- All of this is stored in memory as a structured `package` dictionary passed through the system

### 3. Five Investigators Analyze the Evidence

Each investigator is a Python class that extends a common `Investigator` base class. They run sequentially and never execute untrusted code. Each returns a structured result with `agent`, `status`, `findings`, `evidence`, and `confidence`.

#### Log Investigator
Reads the provided log file line by line. Identifies lines containing error indicators (`ERROR`, `EXCEPTION`, `TRACEBACK`, `FAILED`, `FATAL`). Returns the exact file/line references as evidence.

#### Code Investigator
Scans up to 400 source files across 20+ supported extensions (`.py`, `.js`, `.ts`, `.java`, `.go`, `.rb`, `.php`, `.cs`, `.sql`, etc.). Matches keywords from the user's observation against source code. Identifies relevant files (handlers, services, auth, payment, routes). Returns line-level citations. **Never executes the code.**

#### Change Investigator
Reads the git history file (either from upload or GitHub). Identifies commits correlated with the issue. Returns commit-level evidence references.

#### Pipeline Investigator
Scans for CI/CD workflow files (GitHub Actions `.yml`, GitLab CI, Azure Pipelines). Identifies trigger events, test steps, and deployment steps statically. Reports whether the project has a working test pipeline.

#### Deployment Context Investigator
Looks for Dockerfiles, Docker Compose files, Kubernetes manifests, and Terraform files. Builds a deployment profile describing how the application is containerized and orchestrated.

### 4. Evidence Is Catalogued as Facts

All investigator output flows into the **Evidence Catalog** (`services/evidence_catalog.py`). Every piece of evidence gets:
- A unique `E-NNN` ID (e.g. `E-001`, `E-002`)
- A source type (`log`, `source`, `git`, `pipeline`, `deployment`)
- An `attribution` of `FACT` — meaning it was directly observed, not inferred
- A source file and line number where applicable

This is the foundation of trust. The entire downstream analysis only cites these `E-NNN` IDs.

### 5. The Tribunal Evaluates the Evidence

The Tribunal is the adversarial review system. It consists of three agents:

#### Prosecutor
Builds the strongest possible case for the leading hypothesis. Cites specific `E-NNN` evidence IDs. Constructs a causal chain explaining how the evidence leads to a root cause. Provides a confidence rationale.

#### Defense
Challenges the prosecutor's case. Identifies alternative explanations that haven't been ruled out. Lists missing evidence that would be needed to strengthen or overturn the verdict. Raises the strongest counterargument it can find.

#### Judge
Weighs prosecutor and defense. Issues one of four verdicts:

| Verdict | Meaning |
|---|---|
| `CONFIRMED` | Reproduction succeeded and evidence converges on a single cause |
| `MOST_LIKELY` | Strong evidence supports a leading hypothesis but no reproduction yet |
| `MORE_EVIDENCE_NEEDED` | Multiple hypotheses remain plausible, evidence is insufficient |
| `REJECTED` | The leading hypothesis is contradicted by reproduction data |

Each verdict also includes a **confidence score** (0.0 to 1.0), a **leading hypothesis**, a list of **supporting evidence**, a list of **evidence limitations**, **alternative explanations**, and **recommended next steps**.

### 6. The Trust Layer Is Assembled and Validated

All facts, the hypothesis, tribunal output, and verification status are combined into a `trust_layer` structure. This structure is validated against a **JSON Schema contract** using `jsonschema`. If the trust layer is malformed in any way, validation errors are surfaced in the response. In a correctly running investigation, `validation_errors` is always `[]`.

### 7. Timeline and Pattern Detection Run

**Timeline Builder**: Extracts timestamped events from logs and git history. Classifies events as `ERROR`, `WARNING`, `DEPLOYMENT`, `CODE_CHANGE`, `INCIDENT`, or `INVESTIGATION`. The result is a chronological timeline shown on the dashboard.

**Pattern Detector**: Scans source code for dangerous patterns similar to the root cause being investigated:
- `falsy_value_validation` — `if not value:` style checks that reject valid zero values (MEDIUM risk)
- `loose_equality` — comparisons that may not distinguish between falsy values (LOW risk)
- `catch_all_exception` — broad `except:` handlers that mask errors (MEDIUM risk)
- `silent_failure` — `except: pass` that silently discards exceptions (HIGH risk)

Each detected pattern gets a `PAT-NNNNN` ID, a risk level badge, a confidence score, and a file/line reference.

### 8. Project Profile Is Detected Automatically

The **Project Analyzer** inspects the uploaded source without the user needing to declare anything:
- Detects primary programming language (Python, JavaScript, TypeScript, Java, Go, Ruby, etc.)
- Detects frameworks (Flask, Django, FastAPI, Express, React, Vue, Angular, Spring, Rails, Laravel, Next.js)
- Identifies test frameworks (Pytest, Unittest, Jest)
- Lists entry points (`app.py`, `main.py`, `server.py`, `index.js`)
- Lists dependency files (`requirements.txt`, `package.json`, `pom.xml`)
- Detects Docker, Docker Compose, Kubernetes, Terraform, and CI/CD pipeline presence
- Reports detection confidence

### 9. The Dashboard Renders the Full Report

The single-page frontend (built with plain HTML/CSS/JavaScript, no frontend framework) renders the entire investigation result as a structured dashboard with these sections:

- **Project Profile** — language, framework, entry points, file counts, deployment topology
- **Evidence Status** — which evidence types were available and which were missing
- **Incident Timeline** — chronological view of errors, warnings, deployments, and code changes
- **Investigator Activity** — which of the five investigators ran and what they found
- **Independent Evidence** — the catalogued `E-NNN` facts
- **Tribunal** — prosecutor argument, defense challenges, judge verdict with confidence
- **Confidence Ledger** — facts, hypotheses, alternatives, what would change the verdict
- **Similar Patterns** — risky code patterns found with risk badges and human-review warnings
- **Proof** — RED → GREEN reproduction (demo only) or a safe reproduction plan (user investigations)

---

## The Demo Incident

BugSleuth ships with a built-in demonstration that shows the full workflow end-to-end. The demo scenario is a **payment processing service** with a real, intentional bug:

```python
# The buggy version (sample_app/payment_service.py)
def process_payment(payment_amount: float) -> str:
    if not payment_amount:          # BUG: falsy check rejects valid zero-value payments
        raise ValueError("Invalid payment amount")
    return "Payment processed"
```

A payment of `0` (zero) is valid in a promotional flow. But `if not 0` evaluates to `True` in Python, so the function incorrectly rejects it. BugSleuth's demo detects this, traces the bug through logs and git history, reproduces it with a RED test, applies the fix (`if payment_amount is None:`), and runs a GREEN test — all against a **temporary copy** of the demo files. The original is never changed.

**Crucially:** this RED → GREEN execution runs only for the bundled trusted demo. User-uploaded and GitHub code is **never executed under any circumstances.**

---

## Safety and Trust Design

These principles are non-negotiable in BugSleuth's design:

| Principle | How It Is Enforced |
|---|---|
| **No untrusted code execution** | Only `sample_app/` in a temp directory is ever executed |
| **No speculation** | Every claim cites `E-NNN` evidence IDs; no conclusion without cited facts |
| **Honest about gaps** | `MORE_EVIDENCE_NEEDED` verdict when evidence is insufficient |
| **Transparent reasoning** | Causal chain, counterarguments, uncertainty all visible on dashboard |
| **File safety** | Zip path traversal detection, 20 MB limits, extension validation |
| **Schema validation** | Trust layer validated against JSON Schema contract on every run |

---

## Technology Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.12+, Flask 3.x |
| **Frontend** | Vanilla HTML5 / CSS3 / JavaScript (no framework) |
| **Testing** | Pytest 8.x |
| **Schema validation** | `jsonschema` (Draft 7) |
| **GitHub integration** | Python `urllib` (no third-party HTTP library) |
| **Storage** | Local filesystem (`uploads/`), in-memory dict (Flask process) |
| **Execution** | `subprocess` + `tempfile` (demo only, trusted copy) |

**Zero external AI API calls.** The entire system is deterministic and runs offline.

---

## Project Structure

```
BugSleuth/
├── app.py                          # Flask app, API routes, request handling
├── run.py                          # One-command startup script
├── requirements.txt                # Flask, Pytest, jsonschema
├── pytest.ini                      # Test configuration
│
├── investigators/                  # Five specialized investigation agents
│   ├── base.py                     # Abstract Investigator base class
│   ├── log_investigator.py         # Application log analysis
│   ├── code_investigator.py        # Static source code inspection
│   ├── change_investigator.py      # Git history analysis
│   ├── pipeline_investigator.py    # CI/CD pipeline inspection
│   └── deployment_context_investigator.py  # Docker/K8s/Terraform detection
│
├── tribunal/                       # Adversarial reasoning system
│   ├── prosecutor.py               # Builds strongest case for hypothesis
│   ├── defense.py                  # Challenges hypothesis, finds alternatives
│   └── judge.py                    # Issues final verdict with confidence
│
├── services/                       # Core analysis and orchestration
│   ├── investigation_service.py    # Master pipeline orchestrator
│   ├── project_analyzer.py         # Auto-detects language/framework/tooling
│   ├── timeline_builder.py         # Extracts chronological event timeline
│   ├── pattern_detector.py         # Finds risky code patterns
│   ├── evidence_catalog.py         # Assigns E-NNN IDs to investigator findings
│   ├── trust_schema.py             # JSON Schema validation for trust layer
│   ├── investigation_summary.py    # Readiness scores, activity timeline
│   ├── file_service.py             # Upload handling, zip extraction
│   └── github_service.py           # GitHub API integration
│
├── models/                         # Domain data models
│   ├── evidence.py                 # Evidence class with strength levels
│   ├── hypothesis.py               # Hypothesis class with status tracking
│   ├── incident_timeline.py        # Timeline and event models
│   ├── project_profile.py          # ProjectProfile model
│   └── similar_patterns.py         # SimilarPattern model with risk levels
│
├── utils/
│   └── evidence_builder.py         # Factory for creating Evidence objects
│
├── verification/
│   └── trusted_demo.py             # RED → GREEN pytest execution (demo only)
│
├── templates/
│   ├── index.html                  # Main single-page application
│   ├── about.html                  # About page
│   └── help.html                   # Help/guide page
│
├── static/
│   ├── script.js                   # Frontend investigation flow logic
│   └── style.css                   # IBM-inspired design system
│
├── sample_app/
│   └── payment_service.py          # Seeded buggy demo service
│
├── incident_data/                  # Demo incident payloads (logs, git history, JSON)
├── tests/                          # Automated test suite
│   ├── test_units.py               # Unit tests for all models and services
│   ├── test_integration.py         # Integration tests (10 test classes)
│   └── test_v2.py                  # End-to-end API scenario tests
└── uploads/                        # Runtime upload storage (not committed)
```

---

## Testing

BugSleuth has a comprehensive three-layer test suite covering every major component:

### Unit Tests (`tests/test_units.py`)
Tests every model and service in isolation:
- `Evidence`, `Hypothesis`, `IncidentTimeline`, `SimilarPattern`, `ProjectProfile` models — including round-trip serialization, clamping, and enum validation
- `EvidenceBuilder` — sequential ID generation, factory methods
- `build_evidence_catalog` — ID assignment, source type mapping, skipping unavailable investigators
- `validate_trust_layer` — JSON Schema contract validation
- `TimelineBuilder` — log parsing, git history parsing, event type classification
- `PatternDetector` — all four pattern types, max results limit, unique IDs, excerpt truncation
- `InvestigationReadiness` — score calculation, thresholds
- `EvidenceStrength` — percentage scoring, source counting
- `InvestigationActivityTimeline` — agent ordering, icon assignment
- `FileService` — directory creation, log saving, zip extraction, path traversal rejection

### Integration Tests (`tests/test_integration.py`)
Tests how components work together:
- Investigators → Evidence Catalog
- Evidence Catalog → Tribunal (Prosecutor / Defense / Judge)
- Full `run_investigation` pipeline (observation-only, log-only, source-only, combined)
- File service → Investigation package → `run_investigation`
- Timeline Builder → IncidentTimeline model
- Pattern Detector → investigation result `similar_patterns`
- Project Analyzer → `project_discovery` in investigation result
- Flask API HTTP end-to-end (create + run, log upload, zip upload, no-evidence 400)
- Trust layer validation on live output (demo and user)
- Verification guard (non-demo always returns 403)

### API / Scenario Tests (`tests/test_v2.py`)
End-to-end scenario coverage:
- Observation-only investigation is conservative (`MORE_EVIDENCE_NEEDED`)
- Log-only investigation uses supplied line numbers
- UTF-16 encoded log upload is handled correctly
- Invalid file type and path-traversal zip are rejected
- Valid GitHub URL is accepted; invalid is rejected with the right error
- GitHub repo evidence is included in the investigation package
- GitHub repo investigation runs conservatively
- User investigation never leaks demo data
- Trust layer has auditable facts and valid contract
- User code verification is explicitly unavailable (403)
- Pipeline Investigator detects GitHub Actions and test steps
- Deployment Investigator detects Docker and Kubernetes
- Project without DevOps files is handled gracefully

Run all tests with:
```powershell
pytest -q
```

---

## How Bob (IBM Bob AI) Was the Foundation of This Project

IBM Bob was not just a tool used during development — **Bob was the architect, engineer, debugger, tester, and documentation author** of BugSleuth. Every single layer of this project was built with Bob as the primary engineering agent.

Here is a detailed account of what Bob did:

### Architecture Design
Bob designed the entire system architecture from scratch. The layered design — investigators → evidence catalog → tribunal → trust layer — was conceived and structured by Bob. Bob decided on the abstract `Investigator` base class pattern that makes each investigator independently testable and swappable with future IBM AI agents. Bob designed the separation between the `models/`, `services/`, `investigators/`, `tribunal/`, `utils/`, and `verification/` packages — each with a clear responsibility boundary.

### Backend Development
Bob wrote every Python file in this project:
- The entire Flask application (`app.py`) including all API routes, file upload handling, GitHub URL validation, and the investigation lifecycle
- All five investigator classes — `LogInvestigator`, `CodeInvestigator`, `ChangeInvestigator`, `PipelineInvestigator`, `DeploymentContextInvestigator`
- The complete `investigation_service.py` pipeline orchestrator that wires all investigators, tribunal, timeline, patterns, and trust layer together
- All three tribunal agents — `Prosecutor`, `Defense`, `Judge` — with their evidence-citing logic and multi-mode verdict system
- The `ProjectAnalyzer` service with support for 15+ programming languages and 11+ frameworks
- The `TimelineBuilder` service with multi-format timestamp parsing and event classification
- The `PatternDetector` service with four regex-based pattern types and risk scoring
- The `EvidenceCatalog` service that assigns sequential `E-NNN` IDs to all investigator findings
- The `TrustSchema` validator using JSON Schema Draft 7 via `jsonschema`
- The `InvestigationSummary`, `RecommendedActions`, `EvidenceStrength`, `InvestigationReadiness`, and `InvestigationActivityTimeline` services
- The `GitHubService` with full GitHub API integration (no third-party HTTP library), file tree fetching, raw file downloading, commit history extraction
- The `FileService` with upload validation, path-traversal detection, zip extraction
- All domain models: `Evidence`, `Hypothesis`, `IncidentTimeline`, `TimelineEvent`, `SimilarPattern`, `ProjectProfile` — each with full serialization, deserialization, and validation
- The `EvidenceBuilder` utility with factory methods for every evidence type
- The `trusted_demo.py` RED → GREEN verification engine using subprocess and tempfile

### Frontend Development
Bob designed and built the entire frontend from scratch — no frameworks, no component libraries:
- The complete single-page `index.html` with multi-section layout (landing, submission form, progress screen, dashboard)
- A full `script.js` that handles the entire investigation lifecycle: form submission, file upload with size validation, GitHub URL submission, progress animation, result rendering, demo modal, back navigation, and form reset
- A complete `style.css` implementing an IBM-inspired design system with responsive layout, timeline visualization, evidence cards, tribunal display, pattern risk badges, progress indicators, modal overlays, and navigation
- The `about.html` and `help.html` pages

### Test Suite
Bob wrote all 100+ tests across three test files:
- Every unit test for every model class
- Every unit test for every service
- All 10 integration test classes covering each pipeline boundary
- All API scenario tests including edge cases, security rejections, and data isolation
- The `FakeUpload` test double used to simulate Werkzeug file uploads without actually using Flask's test infrastructure for file I/O

### Debugging and Fixes
Bob diagnosed and fixed every bug that appeared during development. Notable examples:
- The falsy-check demo bug itself (`if not payment_amount:` vs `if payment_amount is None:`) — Bob identified the exact pattern and built the entire RED → GREEN verification around it
- File encoding issues in log reading (UTF-8 BOM vs UTF-16) — Bob added the multi-encoding fallback in `LogInvestigator`
- Path traversal vulnerability in zip extraction — Bob added the `../../` detection guard
- Trust layer schema contract mismatches — Bob designed and implemented the JSON Schema validation layer
- Test isolation issues where investigation IDs were colliding — Bob ensured each test gets independent state
- Silent test failures where `except: pass` was masking errors — Bob added the `silent_failure` pattern detector to catch exactly this

### Versioning and Iterative Improvement
Bob drove the project through multiple versions:
- **v1–v3**: Core investigator and tribunal pipeline
- **v4**: Added `ProjectAnalyzer`, `TimelineBuilder`, `PatternDetector`, structured evidence models, `EvidenceStrength` enum, `Hypothesis` model, and full frontend for these new sections
- **v5**: UX improvements — demo modal, back navigation, file size validation, multi-investigation support
- **v6**: Added `InvestigationSummary`, `RecommendedActions`, `EvidenceStrength` service, `InvestigationActivityTimeline`, trust layer schema validation, and the complete integration test suite

### IBM Bob Integration Architecture
Bob designed BugSleuth so that every deterministic service is a clean drop-in replacement point for a real IBM Bob AI agent. The documented integration points are:

| Current Deterministic Service | Future IBM Bob Agent |
|---|---|
| `ProjectAnalyzer` | IBM Bob project understanding subagent |
| `TimelineBuilder` | IBM Bob event extraction agent |
| `PatternDetector` | IBM Bob pattern analysis agent |
| `LogInvestigator` | IBM Bob log analysis agent |
| `CodeInvestigator` | IBM Bob code understanding agent |
| `ChangeInvestigator` | IBM Bob change analysis agent |
| `Prosecutor` | IBM Bob case-building reasoning agent |
| `Defense` | IBM Bob counter-argument generation agent |
| `Judge` | IBM Bob verdict reasoning agent |

The abstract `Investigator` base class (`investigators/base.py`) defines the exact interface that any IBM Bob agent would implement to slot directly into the pipeline.

---

## Quick Start

```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the application
python run.py

# 4. Open in browser
# http://127.0.0.1:5000/
```

---

## Key Design Principles

1. **Evidence first, speculation never** — No conclusion without an `E-NNN` citation
2. **Honest under-confidence** — Better to say "need more evidence" than to guess
3. **No untrusted execution** — User code is analyzed statically only
4. **Local-only, zero setup friction** — One command, no external services
5. **IBM Bob-ready architecture** — Every service is a clean interface for AI agent substitution
6. **Tested at every layer** — Unit, integration, and API scenario tests
7. **Transparent reasoning** — Every verdict shows its causal chain, confidence, and what would change it

---

*Built for IBM TechXchange 2026 — engineered entirely with IBM Bob as the AI development foundation.*
