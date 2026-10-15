import math
from collections.abc import Generator

import simpy

from dock_scheduling.decision import validate_batch
from dock_scheduling.domain import ScenarioDefinition
from dock_scheduling.event_log import EventLog, EventType
from dock_scheduling.runtime import (
    DockStatus,
    JobRuntime,
    JobStatus,
    create_runtime_state,
)
from dock_scheduling.scheduler import Scheduler
from dock_scheduling.scheduling_state import build_scheduling_state

DAY_END_MIN = 1440


class WarehouseSimulation:
    def __init__(self, scenario: ScenarioDefinition, scheduler: Scheduler) -> None:
        self._env = simpy.Environment()
        self._scheduler = scheduler
        self._plan = scenario.plan
        self._decision_requested = False
        self.runtime = create_runtime_state(scenario)
        self.event_log = EventLog()
        # Hidden realization. Never copied into runtime.
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
        end_min = math.inf if until_min is None else until_min
        while self._env.peek() < end_min:
            current_min = self._env.peek()
            # Process the whole minute before the scheduler sees the state.
            while self._env.peek() == current_min:
                self._env.step()
            if self._decision_requested:
                self._decision_requested = False
                self._decide(int(current_min))

    def _start_service(self, job_id: str, dock_id: str) -> None:
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

    def _decide(self, current_min: int) -> None:
        state = build_scheduling_state(current_min, self._plan, self.runtime)
        decisions = self._scheduler.schedule(state)
        validate_batch(decisions, self.runtime)
        for decision in decisions:
            self._start_service(decision.job_id, decision.dock_id)

    def _arrive(
        self, job_id: str, actual_arrival_min: int
    ) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(actual_arrival_min)
        now_min = int(self._env.now)
        self.runtime.jobs[job_id] = JobRuntime(job_id, JobStatus.WAITING, now_min)
        self.event_log.record(now_min, EventType.JOB_ARRIVAL, job_id)
        self._decision_requested = True

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
        self._decision_requested = True
