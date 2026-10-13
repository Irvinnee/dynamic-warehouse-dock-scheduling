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
    """Read-only view of one simulation minute for the scheduler.

    Tuple order carries no scheduling meaning. Schedulers apply their own ordering.
    """

    current_time_min: int
    waiting_jobs: tuple[WaitingJobView, ...]
    free_docks: tuple[FreeDockView, ...]


def build_scheduling_state(
    current_time_min: int, plan: PlanSnapshot, runtime: RuntimeState
) -> SchedulingState:
    # Takes only the plan, so realization data cannot reach the scheduler.
    plan_by_id = {job.job_id: job for job in plan.jobs}
    waiting_jobs = []
    for job_id in runtime.waiting_job_ids:
        job_plan = plan_by_id[job_id]
        waiting_jobs.append(
            WaitingJobView(
                job_id=job_id,
                observed_arrival_min=runtime.jobs[job_id].observed_arrival_min,
                priority=job_plan.priority,
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
