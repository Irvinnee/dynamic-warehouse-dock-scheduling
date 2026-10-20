from typing import Protocol

from dock_scheduling.decision import Assign
from dock_scheduling.scheduling_state import SchedulingState


class Scheduler(Protocol):
    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]: ...


class FCFSScheduler:
    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        eligible_jobs = sorted(
            state.eligible_jobs, key=lambda job: (job.eligible_since_min, job.job_id)
        )
        free_docks = sorted(state.free_docks, key=lambda dock: dock.dock_id)
        return tuple(
            Assign(job.job_id, dock.dock_id)
            for job, dock in zip(eligible_jobs, free_docks)
        )
