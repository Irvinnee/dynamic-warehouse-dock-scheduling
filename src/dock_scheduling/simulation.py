from collections.abc import Generator

import simpy

from dock_scheduling.domain import ScenarioDefinition
from dock_scheduling.event_log import EventLog, EventType
from dock_scheduling.runtime import (
    DockStatus,
    JobRuntime,
    JobStatus,
    create_runtime_state,
)

DAY_END_MIN = 1440


class WarehouseSimulation:
    """One simulation run of a scenario. Create a new instance for every run."""

    def __init__(self, scenario: ScenarioDefinition) -> None:
        self._env = simpy.Environment()
        self.runtime = create_runtime_state(scenario)
        self.event_log = EventLog()
        # Hidden realization, used only to execute service. Never copied into runtime.
        self._actual_service_time_min = {
            realization.job_id: realization.actual_service_time_min
            for realization in scenario.realization.jobs
        }
        for realization in scenario.realization.jobs:
            if realization.actual_arrival_min < DAY_END_MIN:
                self._env.process(
                    self._arrive(realization.job_id, realization.actual_arrival_min)
                )

    def run(self, until_min: int | None = None) -> None:
        """Process events up to, but not including, those at until_min."""
        self._env.run(until=until_min)

    def start_service(self, job_id: str, dock_id: str) -> None:
        """Start non-preemptive service at the current minute.

        The caller must pass an arrived WAITING job and a FREE dock.
        """
        now_min = int(self._env.now)
        job = self.runtime.jobs[job_id]
        job.status = JobStatus.IN_SERVICE
        job.service_start_min = now_min
        job.assigned_dock_id = dock_id
        dock = self.runtime.docks[dock_id]
        dock.status = DockStatus.BUSY
        dock.current_job_id = job_id
        self.event_log.record(now_min, EventType.SERVICE_START, job_id, dock_id)
        self._env.process(self._serve(job_id, dock_id))

    def _arrive(
        self, job_id: str, actual_arrival_min: int
    ) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(actual_arrival_min)
        now_min = int(self._env.now)
        self.runtime.jobs[job_id] = JobRuntime(job_id, JobStatus.WAITING, now_min)
        self.event_log.record(now_min, EventType.JOB_ARRIVAL, job_id)

    def _serve(self, job_id: str, dock_id: str) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(self._actual_service_time_min[job_id])
        now_min = int(self._env.now)
        job = self.runtime.jobs[job_id]
        job.status = JobStatus.COMPLETED
        job.service_end_min = now_min
        dock = self.runtime.docks[dock_id]
        dock.status = DockStatus.FREE
        dock.current_job_id = None
        self.event_log.record(now_min, EventType.SERVICE_END, job_id, dock_id)
