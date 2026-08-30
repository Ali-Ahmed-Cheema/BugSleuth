"""
Timeline builder service for extracting events from logs and git history.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from models import IncidentTimeline, TimelineEvent, EventType


class TimelineBuilder:
    """Builds incident timeline from logs and git history."""

    # Common timestamp patterns
    TIMESTAMP_PATTERNS = [
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",  # ISO format
        r"\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2}",  # MM/DD/YYYY HH:MM:SS
        r"\w{3} \d{1,2} \d{2}:\d{2}:\d{2}",  # Mon DD HH:MM:SS
    ]

    ERROR_KEYWORDS = ["error", "exception", "failed", "failure", "crash", "critical", "fatal", "panic"]
    WARNING_KEYWORDS = ["warning", "warn", "deprecated", "caution", "attention"]
    DEPLOYMENT_KEYWORDS = ["deploy", "release", "version", "upgrade", "updated", "pushed", "merged"]

    @staticmethod
    def build_timeline(investigation_id: str, logs_path: Optional[Path] = None, history_path: Optional[Path] = None) -> IncidentTimeline:
        """Build a timeline from available evidence."""
        timeline = IncidentTimeline(investigation_id)

        # Parse logs if available
        if logs_path and logs_path.exists():
            TimelineBuilder._parse_logs(logs_path, timeline)

        # Parse git history if available
        if history_path and history_path.exists():
            TimelineBuilder._parse_git_history(history_path, timeline)

        return timeline

    @staticmethod
    def _parse_logs(logs_path: Path, timeline: IncidentTimeline) -> None:
        """Extract events from application logs."""
        try:
            content = logs_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            for index, line in enumerate(lines[:500]):  # Limit to first 500 lines
                line_lower = line.lower()

                # Extract timestamp if present
                timestamp = None
                for pattern in TimelineBuilder.TIMESTAMP_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        timestamp = match.group(0)
                        break

                # Classify event type
                event_type = EventType.UNKNOWN
                if any(keyword in line_lower for keyword in TimelineBuilder.ERROR_KEYWORDS):
                    event_type = EventType.ERROR
                elif any(keyword in line_lower for keyword in TimelineBuilder.WARNING_KEYWORDS):
                    event_type = EventType.WARNING
                elif any(keyword in line_lower for keyword in TimelineBuilder.DEPLOYMENT_KEYWORDS):
                    event_type = EventType.DEPLOYMENT

                # Create event for significant lines
                if event_type != EventType.UNKNOWN:
                    event = TimelineEvent(
                        event_id=f"LOG-{index:05d}",
                        event_type=event_type,
                        description=line.strip()[:200],  # Limit description
                        timestamp=timestamp,
                        source="Application Log",
                        details={"line_number": index + 1},
                    )
                    timeline.add_event(event)

        except Exception:
            pass

    @staticmethod
    def _parse_git_history(history_path: Path, timeline: IncidentTimeline) -> None:
        """Extract events from git history."""
        try:
            content = history_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            commit_counter = 0
            for line in lines[:200]:  # Limit to first 200 lines
                line = line.strip()

                # Look for commit hashes (typically 40-char hex)
                if re.match(r"^[a-f0-9]{7,40}\s", line):
                    commit_counter += 1
                    # Extract commit message
                    parts = line.split(None, 1)
                    commit_hash = parts[0]
                    message = parts[1] if len(parts) > 1 else "Commit"

                    # Try to extract timestamp
                    timestamp_match = re.search(r"\d{4}-\d{2}-\d{2}", line)
                    timestamp = timestamp_match.group(0) if timestamp_match else None

                    event = TimelineEvent(
                        event_id=f"GIT-{commit_counter:05d}",
                        event_type=EventType.CODE_CHANGE,
                        description=message[:200],
                        timestamp=timestamp,
                        source="Git History",
                        details={"commit": commit_hash},
                    )
                    timeline.add_event(event)

        except Exception:
            pass

    @staticmethod
    def add_incident_event(timeline: IncidentTimeline, timestamp: Optional[str] = None) -> None:
        """Add incident reported event."""
        event = TimelineEvent(
            event_id="INCIDENT-001",
            event_type=EventType.INCIDENT,
            description="Incident reported",
            timestamp=timestamp or datetime.now().isoformat(),
            source="Investigation",
        )
        timeline.add_event(event)

    @staticmethod
    def add_investigation_start(timeline: IncidentTimeline, timestamp: Optional[str] = None) -> None:
        """Add investigation started event."""
        event = TimelineEvent(
            event_id="INVESTIGATION-001",
            event_type=EventType.INVESTIGATION,
            description="BugSleuth investigation started",
            timestamp=timestamp or datetime.now().isoformat(),
            source="Investigation",
        )
        timeline.add_event(event)
