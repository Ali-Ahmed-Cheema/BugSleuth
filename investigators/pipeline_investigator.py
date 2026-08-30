from pathlib import Path
import re

from .base import Investigator


class PipelineInvestigator(Investigator):
    def __init__(self, source_path: Path):
        self.source_path = source_path

    def investigate(self, incident: dict) -> dict:
        findings = []
        evidence = []
        workflow_files = []
        triggers = []
        test_steps = []
        deployment_steps = []
        pipeline_detected = False

        if self.source_path and self.source_path.exists():
            if self.source_path.is_dir():
                workflow_files = sorted(
                    list(self.source_path.rglob(".github/workflows/*.yml"))
                    + list(self.source_path.rglob(".github/workflows/*.yaml"))
                    + list(self.source_path.rglob("**/.gitlab-ci.yml"))
                    + list(self.source_path.rglob("**/azure-pipelines*.yml"))
                )
            elif self.source_path.name.lower().endswith((".yml", ".yaml")):
                workflow_files = [self.source_path]

        if workflow_files:
            pipeline_detected = True
            findings.append("Pipeline configuration detected.")
            findings.append("GitHub Actions or CI workflow files were found and inspected statically.")
        else:
            findings.append("No supported CI/CD configuration was detected in the supplied project.")

        for workflow_file in workflow_files[:20]:
            try:
                content = workflow_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lines = content.splitlines()
            for index, line in enumerate(lines[:200], 1):
                lowered = line.lower()
                if re.search(r"\b(on|push|pull_request|workflow_dispatch|schedule)\b", lowered):
                    triggers.append(f"{workflow_file.name}:{index}: {line.strip()}")
                if any(token in lowered for token in ["pytest", "npm test", "go test", "mvn test", "gradle test", "npm run test"]):
                    test_steps.append(f"{workflow_file.name}:{index}: {line.strip()}")
                if any(token in lowered for token in ["deploy", "docker build", "kubectl", "helm", "aws", "gcloud", "terraform apply"]):
                    deployment_steps.append(f"{workflow_file.name}:{index}: {line.strip()}")
                if any(token in lowered for token in ["run:", "uses:"]):
                    evidence.append(f"{workflow_file.name}:{index}: {line.strip()}")

        if pipeline_detected:
            if triggers:
                findings.append(f"Trigger configuration detected: {len(triggers)} relevant workflow trigger line(s).")
            else:
                findings.append("Workflow trigger configuration was present but no explicit trigger lines were readable in the inspected files.")

            if test_steps:
                findings.append("Test stage detected in pipeline configuration.")
            else:
                findings.append("No test execution command was clearly identified in the pipeline files inspected.")

            if deployment_steps:
                findings.append("Deployment-related step detected in pipeline configuration.")
            else:
                findings.append("No deployment step was clearly identified in the available pipeline configuration.")

        return {
            "agent": "Pipeline Investigator",
            "status": "complete",
            "pipeline_detected": pipeline_detected,
            "findings": findings,
            "evidence": evidence[:20] or (triggers[:5] + test_steps[:5] + deployment_steps[:5]),
            "confidence": 0.82 if pipeline_detected else 0.12,
            "workflow_files": [str(path.relative_to(self.source_path)) if self.source_path and self.source_path.is_dir() and path.is_relative_to(self.source_path) else path.name for path in workflow_files[:10]],
            "trigger_events": triggers[:10],
            "test_steps": test_steps[:10],
            "deployment_steps": deployment_steps[:10],
            "execution_result_available": False,
        }
