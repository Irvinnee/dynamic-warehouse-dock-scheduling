from dataclasses import dataclass
from enum import Enum

from dock_scheduling.domain import JobPlan, ScenarioDefinition


class JobStatus(Enum):
    WAITING = "WAITING"
    RELOCATING = "RELOCATING"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"


class DockStatus(Enum):
    FREE = "FREE"
    BUSY = "BUSY"


@dataclass
class TruckRuntime:
    truck_id: str
    observed_arrival_min: int
    jobs: tuple[JobPlan, ...]
    priority: bool
    current_job_index: int = 0
    completed_min: int | None = None


@dataclass
class JobRuntime:
    job_id: str
    truck_id: str
    status: JobStatus
    eligible_since_min: int
    service_start_min: int | None = None
    service_end_min: int | None = None
    assigned_dock_id: str | None = None
    assigned_min: int | None = None


@dataclass
class DockRuntime:
    dock_id: str
    status: DockStatus = DockStatus.FREE
    current_job_id: str | None = None


@dataclass
class RuntimeState:
    trucks: dict[str, TruckRuntime]
    jobs: dict[str, JobRuntime]
    docks: dict[str, DockRuntime]

    @property
    def eligible_job_ids(self) -> list[str]:
        return [
            job.job_id for job in self.jobs.values() if job.status is JobStatus.WAITING
        ]


def previous_dock_id(runtime: RuntimeState, truck: TruckRuntime) -> str | None:
    if truck.current_job_index == 0:
        return None
    previous_job_id = truck.jobs[truck.current_job_index - 1].job_id
    return runtime.jobs[previous_job_id].assigned_dock_id


def create_runtime_state(scenario: ScenarioDefinition) -> RuntimeState:
    return RuntimeState(
        trucks={},
        jobs={},
        docks={dock.dock_id: DockRuntime(dock.dock_id) for dock in scenario.docks},
    )
