from dataclasses import dataclass

from dock_scheduling.domain import OperationType, PlanSnapshot
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
    current_time_min: int, plan: PlanSnapshot, runtime: RuntimeState
) -> SchedulingState:
    # takes only the plan, realization data never reaches the scheduler
    planned_by_job_id = {
        job.job_id: (truck, job) for truck in plan.trucks for job in truck.jobs
    }
    eligible_jobs = []
    for job_id in runtime.eligible_job_ids:
        truck_plan, job_plan = planned_by_job_id[job_id]
        eligible_jobs.append(
            EligibleJobView(
                job_id=job_id,
                truck_id=truck_plan.truck_id,
                operation=job_plan.operation,
                section=job_plan.section,
                priority=truck_plan.priority,
                estimated_service_time_min=job_plan.estimated_service_time_min,
                eligible_since_min=runtime.jobs[job_id].eligible_since_min,
                previous_dock_id=previous_dock_id(
                    runtime, runtime.trucks[truck_plan.truck_id], truck_plan.jobs
                ),
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
