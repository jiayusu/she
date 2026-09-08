"""Versioned learning-event boundary and conservative mastery promotion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    RAW_OBSERVATION = "raw_observation"
    CANDIDATE_EVIDENCE = "candidate_evidence"
    CONFIRMED_MASTERY = "confirmed_mastery"


class EvidenceStatus(str, Enum):
    OBSERVED_ONCE = "OBSERVED_ONCE"
    REPEATED = "REPEATED"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class MasteryEvidence:
    event_id: str
    expression: str
    target_reached: bool
    spontaneous: bool
    scaffold_level: int
    assessment_confidence: float
    status: EvidenceStatus = EvidenceStatus.OBSERVED_ONCE

    def as_event_patch(self) -> dict[str, Any]:
        """Return only fields permitted on the shared wire contract."""
        return {
            "event_id": self.event_id,
            "event_kind": EventKind.CANDIDATE_EVIDENCE.value,
            "evidence_status": self.status.value,
            "assessment": {
                "target_reached": self.target_reached,
                "semantic_correctness": 1.0 if self.target_reached else 0.0,
                "spontaneous": self.spontaneous,
                "assessment_confidence": self.assessment_confidence,
            },
        }


def can_confirm(evidence: list[MasteryEvidence], *, min_confidence: float = 0.8) -> bool:
    """Require repeated high-confidence evidence; one error never confirms a weakness."""
    qualifying = [e for e in evidence if e.target_reached and e.assessment_confidence >= min_confidence]
    return len(qualifying) >= 2 and any(e.spontaneous and e.scaffold_level <= 2 for e in qualifying)


def next_status(evidence: list[MasteryEvidence]) -> EvidenceStatus:
    if can_confirm(evidence):
        return EvidenceStatus.CONFIRMED
    if len(evidence) >= 2:
        return EvidenceStatus.REPEATED
    return EvidenceStatus.OBSERVED_ONCE
