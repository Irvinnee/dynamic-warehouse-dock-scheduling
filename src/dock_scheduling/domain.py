from dataclasses import dataclass
from enum import Enum

MINUTES_PER_DAY = 1440


class OperationType(Enum):
    LOAD = "LOAD"
    UNLOAD = "UNLOAD"


@dataclass(frozen=True)
class JobPlan:
    job_id: str
    operation: OperationType
    section: str
    estimated_service_time_min: int


@dataclass(frozen=True)
class TruckPlan:
    truck_id: str
    planned_arrival_min: int
    priority: bool
    # order = processing order
    jobs: tuple[JobPlan, ...]


@dataclass(frozen=True)
class DockDefinition:
    dock_id: str


@dataclass(frozen=True)
class PlanSnapshot:
    trucks: tuple[TruckPlan, ...]


@dataclass(frozen=True)
class TruckRealization:
    truck_id: str
    # None = no-show
    actual_arrival_min: int | None


@dataclass(frozen=True)
class JobRealization:
    job_id: str
    actual_service_time_min: int


@dataclass(frozen=True)
class RealizationDefinition:
    """Actual outcomes, known only to the simulator."""

    trucks: tuple[TruckRealization, ...]
    jobs: tuple[JobRealization, ...]


@dataclass(frozen=True)
class ScenarioDefinition:
    plan: PlanSnapshot
    realization: RealizationDefinition
    docks: tuple[DockDefinition, ...]
    relocation_time_min: int
