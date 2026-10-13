from dataclasses import dataclass
from enum import Enum


class OperationType(Enum):
    LOAD = "LOAD"
    UNLOAD = "UNLOAD"
    BOTH = "BOTH"


@dataclass(frozen=True)
class JobPlan:
    """Planning information that may be visible to the scheduler."""

    job_id: str
    planned_arrival_min: int
    operation: OperationType
    priority: bool
    estimated_service_time_min: int
    unload_section: str | None
    load_section: str | None


@dataclass(frozen=True)
class JobRealization:
    """Actual outcome of a job, private to the simulator."""

    job_id: str
    actual_arrival_min: int
    actual_service_time_min: int


@dataclass(frozen=True)
class DockDefinition:
    dock_id: str


@dataclass(frozen=True)
class PlanSnapshot:
    jobs: tuple[JobPlan, ...]


@dataclass(frozen=True)
class RealizationDefinition:
    jobs: tuple[JobRealization, ...]


@dataclass(frozen=True)
class ScenarioDefinition:
    plan: PlanSnapshot
    realization: RealizationDefinition
    docks: tuple[DockDefinition, ...]
