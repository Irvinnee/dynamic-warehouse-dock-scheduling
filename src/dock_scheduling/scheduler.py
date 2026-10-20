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
        free_dock_ids = sorted(dock.dock_id for dock in state.free_docks)
        selected_jobs = eligible_jobs[: len(free_dock_ids)]

        # previous docks first, otherwise a lowest-id pick could take one
        # (only saves relocation, the selected jobs stay the same)
        dock_id_by_job_id: dict[str, str] = {}
        for job in selected_jobs:
            if (
                job.previous_dock_id is not None
                and job.previous_dock_id in free_dock_ids
            ):
                dock_id_by_job_id[job.job_id] = job.previous_dock_id
                free_dock_ids.remove(job.previous_dock_id)
        for job in selected_jobs:
            if job.job_id not in dock_id_by_job_id:
                dock_id_by_job_id[job.job_id] = free_dock_ids.pop(0)

        return tuple(
            Assign(job.job_id, dock_id_by_job_id[job.job_id]) for job in selected_jobs
        )
