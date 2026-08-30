from pathlib import Path

from .base import Investigator


class DeploymentContextInvestigator(Investigator):
    def __init__(self, source_path: Path):
        self.source_path = source_path

    def investigate(self, incident: dict) -> dict:
        profile = {
            "containerization": "Not detected",
            "orchestration": "Not detected",
            "infrastructure_as_code": "Not detected",
            "cloud_provider": "Not confidently identified",
            "dockerfile_present": False,
            "compose_present": False,
            "kubernetes_files": [],
            "observations": [],
        }
        findings = []
        evidence = []

        if not self.source_path or not self.source_path.exists():
            return {
                "agent": "Deployment Context Investigator",
                "status": "complete",
                "findings": ["No repository or deployment context was supplied."],
                "evidence": [],
                "confidence": 0.0,
                "deployment_profile": profile,
            }

        files = []
        if self.source_path.is_dir():
            files = list(self.source_path.rglob("*"))
        else:
            files = [self.source_path]

        dockerfile = next((path for path in files if path.name.lower() == "dockerfile"), None)
        compose_files = [path for path in files if path.name.lower() in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}]
        k8s_files = [path for path in files if path.name.lower().endswith((".yaml", ".yml")) and any(token in path.name.lower() for token in ["deployment", "service", "ingress", "statefulset", "configmap", "job"]) or ("k8s" in str(path).lower() and path.name.lower().endswith((".yaml", ".yml")))]
        terraform_files = [path for path in files if path.name.lower().endswith((".tf", ".tfvars"))]

        if dockerfile:
            profile["containerization"] = "Docker detected"
            profile["dockerfile_present"] = True
            findings.append("Dockerfile detected; containerization is present in the project configuration.")
            try:
                docker_text = dockerfile.read_text(encoding="utf-8", errors="ignore")
                evidence.append(f"{dockerfile.name}: {docker_text.splitlines()[:8]}" )
                if "FROM " in docker_text:
                    findings.append("Base image configuration was detected in the Dockerfile.")
                if "EXPOSE" in docker_text:
                    findings.append("Port exposure was detected in the Dockerfile.")
                if "CMD" in docker_text or "ENTRYPOINT" in docker_text:
                    findings.append("Container startup command was detected in the Dockerfile.")
            except OSError:
                pass

        if compose_files:
            profile["containerization"] = "Docker detected"
            profile["compose_present"] = True
            findings.append("Docker Compose configuration was detected.")

        if k8s_files:
            profile["orchestration"] = "Kubernetes detected"
            profile["kubernetes_files"] = [path.name for path in k8s_files[:10]]
            findings.append(f"Kubernetes manifests detected: {', '.join(profile['kubernetes_files'])}.")
            for path in k8s_files[:5]:
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                lowered = content.lower()
                if "replicas:" in lowered:
                    findings.append(f"Potential configuration observation: {path.name} includes replica settings and may warrant deployment review.")
                if "kind: service" in lowered:
                    findings.append(f"Potential configuration observation: {path.name} defines a Service resource that routes traffic to pods.")
                if "kind: deployment" in lowered:
                    findings.append(f"Potential configuration observation: {path.name} declares a Deployment resource.")
                if "secret" in lowered or "env:" in lowered:
                    findings.append(f"Configuration review: {path.name} references environment variables or secret-related configuration; no secret values are displayed.")
                evidence.append(f"{path.name}: kubernetes manifest inspected without executing it")

        if terraform_files:
            profile["infrastructure_as_code"] = "Terraform detected"
            findings.append("Infrastructure as code was detected in Terraform files.")

        if not dockerfile and not compose_files and not k8s_files and not terraform_files:
            findings.append("No supported delivery configuration was detected.")

        return {
            "agent": "Deployment Context Investigator",
            "status": "complete",
            "findings": findings,
            "evidence": evidence[:20],
            "confidence": 0.74 if dockerfile or compose_files or k8s_files else 0.1,
            "deployment_profile": profile,
        }
