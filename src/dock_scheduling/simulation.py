import math
from collections.abc import Generator

import simpy

from dock_scheduling.decision import validate_batch
from dock_scheduling.domain import JobPlan, ScenarioDefinition
from dock_scheduling.event_log import EventLog, EventType
from dock_scheduling.runtime import (
    DockStatus,
    JobRuntime,
    JobStatus,
    TruckRuntime,
    create_runtime_state,
    previous_dock_id,
)
from dock_scheduling.scheduler import Scheduler
from dock_scheduling.scheduling_state import build_scheduling_state


class WarehouseSimulation:
    def __init__(self, scenario: ScenarioDefinition, scheduler: Scheduler) -> None:
        self._env = simpy.Environment()
        self._scheduler = scheduler
        self._relocation_time_min = scenario.relocation_time_min
        self._decision_requested = False
        self.runtime = create_runtime_state(scenario)
        self.event_log = EventLog()
        # not in runtime, the scheduler must never see actual service times
        self._actual_service_time_min = {
            realization.job_id: realization.actual_service_time_min
            for realization in scenario.realization.jobs
        }
        planned_by_truck_id = {truck.truck_id: truck for truck in scenario.plan.trucks}
        for realization in scenario.realization.trucks:
            if realization.actual_arrival_min is not None:
                truck = planned_by_truck_id[realization.truck_id]
                self._env.process(
                    self._arrive(
                        truck.truck_id,
                        realization.actual_arrival_min,
                        truck.jobs,
                        truck.priority,
                    )
                )
        for walk_in in scenario.realization.unplanned_trucks:
            self._env.process(
                self._arrive(
                    walk_in.truck_id, walk_in.actual_arrival_min, walk_in.jobs, False
                )
            )

    def run(self, until_min: int | None = None) -> None:
        """Process events up to, but not including, those at until_min."""
        end_min = math.inf if until_min is None else until_min
        while self._env.peek() < end_min:
            current_min = self._env.peek()
            # finish the whole minute before the scheduler looks
            while self._env.peek() == current_min:
                self._env.step()
            if self._decision_requested:
                self._decision_requested = False
                self._decide(int(current_min))

    def _activate_job(self, truck: TruckRuntime, job_index: int) -> None:
        job_id = truck.jobs[job_index].job_id
        truck.current_job_index = job_index
        self.runtime.jobs[job_id] = JobRuntime(
            job_id, truck.truck_id, JobStatus.WAITING, int(self._env.now)
        )

    def _assign(self, job_id: str, dock_id: str) -> None:
        now_min = int(self._env.now)
        job = self.runtime.jobs[job_id]
        truck = self.runtime.trucks[job.truck_id]
        from_dock_id = previous_dock_id(self.runtime, truck)
        job.assigned_min = now_min
        job.assigned_dock_id = dock_id
        # dock is taken already, even while the truck is still relocating
        dock = self.runtime.docks[dock_id]
        dock.status = DockStatus.BUSY
        dock.current_job_id = job_id
        relocates = (
            from_dock_id is not None
            and from_dock_id != dock_id
            and self._relocation_time_min > 0
        )
        if relocates:
            job.status = JobStatus.RELOCATING
            self.event_log.record(
                now_min, EventType.RELOCATION_START, job.truck_id, job_id, dock_id
            )
            self._env.process(self._relocate(job_id, dock_id))
        else:
            self._start_service(job_id, dock_id)

    def _start_service(self, job_id: str, dock_id: str) -> None:
        now_min = int(self._env.now)
        job = self.runtime.jobs[job_id]
        job.status = JobStatus.IN_SERVICE
        job.service_start_min = now_min
        self.event_log.record(
            now_min, EventType.JOB_START, job.truck_id, job_id, dock_id
        )
        self._env.process(self._serve(job_id, dock_id))

    def _decide(self, current_min: int) -> None:
        state = build_scheduling_state(current_min, self.runtime)
        decisions = self._scheduler.schedule(state)
        validate_batch(decisions, self.runtime)
        for decision in decisions:
            self._assign(decision.job_id, decision.dock_id)

    def _arrive(
        self,
        truck_id: str,
        actual_arrival_min: int,
        jobs: tuple[JobPlan, ...],
        priority: bool,
    ) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(actual_arrival_min)
        now_min = int(self._env.now)
        truck = TruckRuntime(truck_id, now_min, jobs, priority)
        self.runtime.trucks[truck_id] = truck
        self._activate_job(truck, 0)
        self.event_log.record(now_min, EventType.TRUCK_ARRIVAL, truck_id)
        self._decision_requested = True

    def _relocate(
        self, job_id: str, dock_id: str
    ) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(self._relocation_time_min)
        # no decision here, nothing got freed or became eligible
        self._start_service(job_id, dock_id)

    def _serve(self, job_id: str, dock_id: str) -> Generator[simpy.Event, None, None]:
        yield self._env.timeout(self._actual_service_time_min[job_id])
        now_min = int(self._env.now)
        job = self.runtime.jobs[job_id]
        job.status = JobStatus.COMPLETED
        job.service_end_min = now_min
        dock = self.runtime.docks[dock_id]
        dock.status = DockStatus.FREE
        dock.current_job_id = None
        self.event_log.record(now_min, EventType.JOB_END, job.truck_id, job_id, dock_id)
        truck = self.runtime.trucks[job.truck_id]
        next_job_index = truck.current_job_index + 1
        if next_job_index < len(truck.jobs):
            self._activate_job(truck, next_job_index)
        else:
            truck.completed_min = now_min
        self._decision_requested = True
