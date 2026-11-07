from dataclasses import dataclass

from dock_scheduling.domain import OperationType
from dock_scheduling.runtime import DockStatus, RuntimeState, previous_dock_id


@dataclass(frozen=True)
class EligibleJobView:
    job_id: str
    truck_id: str
    operation: OperationType
    section: str
    priority: bool
    estimated_service_time_min: int
    eligible_since_min: int
    previous_dock_id: str | None


@dataclass(frozen=True)
class FreeDockView:
    dock_id: str


@dataclass(frozen=True)
class SchedulingState:
    """Tuple order carries no scheduling meaning."""

    current_time_min: int
    eligible_jobs: tuple[EligibleJobView, ...]
    free_docks: tuple[FreeDockView, ...]


def build_scheduling_state(
    current_time_min: int, runtime: RuntimeState
) -> SchedulingState:
    # runtime only has trucks that already arrived, nothing from the future
    eligible_jobs = []
    for job_id in runtime.eligible_job_ids:
        job = runtime.jobs[job_id]
        truck = runtime.trucks[job.truck_id]
        # a waiting job is always its truck's current job
        job_plan = truck.jobs[truck.current_job_index]
        eligible_jobs.append(
            EligibleJobView(
                job_id=job_id,
                truck_id=truck.truck_id,
                operation=job_plan.operation,
                section=job_plan.section,
                priority=truck.priority,
                estimated_service_time_min=job_plan.estimated_service_time_min,
                eligible_since_min=job.eligible_since_min,
                previous_dock_id=previous_dock_id(runtime, truck),
            )
        )
    return SchedulingState(
        current_time_min=current_time_min,
        eligible_jobs=tuple(eligible_jobs),
        free_docks=tuple(
            FreeDockView(dock.dock_id)
            for dock in runtime.docks.values()
            if dock.status is DockStatus.FREE
        ),
    )
