from abc import ABC, abstractmethod


class Investigator(ABC):
    """Stable boundary for deterministic investigators or future Bob subagents."""

    @abstractmethod
    def investigate(self, incident: dict) -> dict:
        raise NotImplementedError