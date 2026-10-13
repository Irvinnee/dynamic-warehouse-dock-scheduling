from dataclasses import dataclass
from enum import Enum

from dock_scheduling.domain import ScenarioDefinition


class JobStatus(Enum):
    WAITING = "WAITING"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"


class DockStatus(Enum):
    FREE = "FREE"
    BUSY = "BUSY"


@dataclass
class JobRuntime:
    job_id: str
    status: JobStatus
    observed_arrival_min: int
    service_start_min: int | None = None
    service_end_min: int | None = None
    assigned_dock_id: str | None = None


@dataclass
class DockRuntime:
    dock_id: str
    status: DockStatus = DockStatus.FREE
    current_job_id: str | None = None


@dataclass
class RuntimeState:
    jobs: dict[str, JobRuntime]
    docks: dict[str, DockRuntime]

    @property
    def waiting_job_ids(self) -> list[str]:
        return [
            job.job_id for job in self.jobs.values() if job.status is JobStatus.WAITING
        ]


def create_runtime_state(scenario: ScenarioDefinition) -> RuntimeState:
    return RuntimeState(
        jobs={},
        docks={dock.dock_id: DockRuntime(dock.dock_id) for dock in scenario.docks},
    )
