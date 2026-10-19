from dataclasses import dataclass

from dock_scheduling.domain import PlanSnapshot
from dock_scheduling.runtime import DockStatus, RuntimeState


@dataclass(frozen=True)
class WaitingJobView:
    job_id: str
    observed_arrival_min: int
    priority: bool
    estimated_service_time_min: int


@dataclass(frozen=True)
class FreeDockView:
    dock_id: str


@dataclass(frozen=True)
class SchedulingState:
    """Tuple order carries no scheduling meaning."""

    current_time_min: int
    waiting_jobs: tuple[WaitingJobView, ...]
    free_docks: tuple[FreeDockView, ...]


def build_scheduling_state(
    current_time_min: int, plan: PlanSnapshot, runtime: RuntimeState
) -> SchedulingState:
    # takes only the plan, realization data never reaches the scheduler
    planned_by_job_id = {
        job.job_id: (truck, job) for truck in plan.trucks for job in truck.jobs
    }
    waiting_jobs = []
    for job_id in runtime.waiting_job_ids:
        truck_plan, job_plan = planned_by_job_id[job_id]
        waiting_jobs.append(
            WaitingJobView(
                job_id=job_id,
                observed_arrival_min=runtime.jobs[job_id].observed_arrival_min,
                priority=truck_plan.priority,
                estimated_service_time_min=job_plan.estimated_service_time_min,
            )
        )
    return SchedulingState(
        current_time_min=current_time_min,
        waiting_jobs=tuple(waiting_jobs),
        free_docks=tuple(
            FreeDockView(dock.dock_id)
            for dock in runtime.docks.values()
            if dock.status is DockStatus.FREE
        ),
    )
