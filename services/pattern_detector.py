"""
Similar patterns detector for finding potentially problematic code patterns.
"""

import re
from pathlib import Path
from typing import Optional, List
from models import SimilarPattern, RiskLevel


class PatternDetector:
    """Detects similar code patterns in a project."""

    # Pattern definitions: (name, regex, risk_level, description_template)
    PATTERNS = [
        # Falsy value validation
        (
            "falsy_value_validation",
            r"if\s+not\s+\w+\s*:",
            RiskLevel.MEDIUM,
            "Potential falsy-value validation that may reject valid zero or empty values"
        ),
        # Loose equality
        (
            "loose_equality",
            r"==\s*(?:null|None|undefined|''|\"\")",
            RiskLevel.LOW,
            "Loose equality check that may not distinguish between falsy values"
        ),
        # Catch-all exception handlers
        (
            "catch_all_exception",
            r"except\s*:|catch\s*\(\s*\w*\s*\)",
            RiskLevel.MEDIUM,
            "Broad exception handler that may mask the root cause"
        ),
        # Silent failures
        (
            "silent_failure",
            r"except\s*:[\s\n]*pass",
            RiskLevel.HIGH,
            "Silent exception handling that logs nothing"
        ),
    ]

    @staticmethod
    def find_similar_patterns(
        source_path: Optional[Path],
        pattern_type: str = "falsy_value_validation",
        max_results: int = 10
    ) -> List[SimilarPattern]:
        """Find similar patterns in source code."""
        
        patterns = []

        if not source_path or not source_path.exists():
            return patterns

        # Find the pattern definition
        pattern_def = None
        for p_name, p_regex, p_risk, p_desc in PatternDetector.PATTERNS:
            if p_name == pattern_type:
                pattern_def = (p_name, p_regex, p_risk, p_desc)
                break

        if not pattern_def:
            return patterns

        name, regex, risk, desc_template = pattern_def

        # Collect files to search
        supported_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb", ".php", ".cs"}
        files = []

        if source_path.is_file():
            files = [source_path]
        else:
            for ext in supported_extensions:
                files.extend(source_path.glob(f"**/*{ext}"))

        files = files[:100]  # Limit to 100 files

        pattern_counter = 0
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()

                for line_num, line in enumerate(lines, 1):
                    if re.search(regex, line, re.IGNORECASE):
                        pattern_counter += 1
                        pattern = SimilarPattern(
                            pattern_id=f"PAT-{pattern_counter:05d}",
                            source_file=str(file_path.relative_to(source_path.parent if source_path.is_dir() else source_path.parent.parent)),
                            line_number=line_num,
                            excerpt=line.strip()[:150],
                            similarity_reason=desc_template,
                            risk_level=risk,
                            match_confidence=0.7,
                        )
                        patterns.append(pattern)

                        if len(patterns) >= max_results:
                            return patterns

            except Exception:
                continue

        return patterns

    @staticmethod
    def find_all_patterns(source_path: Optional[Path], max_results: int = 20) -> List[SimilarPattern]:
        """Find all types of patterns in source code."""
        all_patterns = []

        for pattern_name, _, _, _ in PatternDetector.PATTERNS:
            patterns = PatternDetector.find_similar_patterns(source_path, pattern_name, max_results=5)
            all_patterns.extend(patterns)

        return all_patterns[:max_results]
