"""
Incident timeline model for chronological event tracking.
"""

from enum import Enum
from typing import Optional
from datetime import datetime


class EventType(str, Enum):
    """Type of timeline event."""
    DEPLOYMENT = "DEPLOYMENT"
    ERROR = "ERROR"
    WARNING = "WARNING"
    CODE_CHANGE = "CODE_CHANGE"
    INCIDENT = "INCIDENT"
    INVESTIGATION = "INVESTIGATION"
    UNKNOWN = "UNKNOWN"


class TimelineEvent:
    """Represents a single event in the investigation timeline."""

    def __init__(
        self,
        event_id: str,
        event_type: EventType,
        description: str,
        timestamp: Optional[str] = None,
        source: str = "Unknown",
        details: Optional[dict] = None,
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.description = description
        self.timestamp = timestamp
        self.source = source
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "source": self.source,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimelineEvent":
        """Create TimelineEvent from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data.get("event_type", "UNKNOWN")),
            description=data["description"],
            timestamp=data.get("timestamp"),
            source=data.get("source", "Unknown"),
            details=data.get("details", {}),
        )


class IncidentTimeline:
    """Represents the complete timeline of events for an investigation."""

    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.events: list[TimelineEvent] = []

    def add_event(self, event: TimelineEvent) -> None:
        """Add an event to the timeline."""
        self.events.append(event)

    def get_events_sorted(self) -> list[TimelineEvent]:
        """Get events sorted by timestamp, with undated events at the end."""
        dated = []
        undated = []

        for event in self.events:
            if event.timestamp:
                try:
                    # Try to parse ISO format timestamp
                    dated.append((datetime.fromisoformat(event.timestamp.replace('Z', '+00:00')), event))
                except (ValueError, AttributeError):
                    undated.append(event)
            else:
                undated.append(event)

        # Sort dated events by timestamp
        dated.sort(key=lambda x: x[0])
        sorted_events = [event for _, event in dated] + undated

        return sorted_events

    def to_dict(self) -> dict:
        """Convert timeline to dictionary for JSON serialization."""
        return {
            "investigation_id": self.investigation_id,
            "events": [event.to_dict() for event in self.get_events_sorted()],
            "event_count": len(self.events),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IncidentTimeline":
        """Create IncidentTimeline from dictionary."""
        timeline = cls(data["investigation_id"])
        for event_data in data.get("events", []):
            timeline.add_event(TimelineEvent.from_dict(event_data))
        return timeline
