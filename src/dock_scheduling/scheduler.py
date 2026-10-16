from typing import Protocol

from dock_scheduling.decision import Assign
from dock_scheduling.scheduling_state import SchedulingState


class Scheduler(Protocol):
    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]: ...


class FCFSScheduler:
    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        waiting_jobs = sorted(
            state.waiting_jobs, key=lambda job: (job.observed_arrival_min, job.job_id)
        )
        free_docks = sorted(state.free_docks, key=lambda dock: dock.dock_id)
        return tuple(
            Assign(job.job_id, dock.dock_id)
            for job, dock in zip(waiting_jobs, free_docks)
        )
