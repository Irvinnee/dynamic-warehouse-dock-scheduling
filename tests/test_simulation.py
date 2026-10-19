import pytest

from dock_scheduling.decision import Assign, InvalidDecisionError
from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
    TruckPlan,
    TruckRealization,
)
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.runtime import JobStatus
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.scheduling_state import SchedulingState
from dock_scheduling.simulation import WarehouseSimulation

SERVICE_TIME_MIN = 30


class _ScriptedScheduler:
    def __init__(self, decisions_by_minute: dict[int, tuple[Assign, ...]]) -> None:
        self._decisions_by_minute = decisions_by_minute
        self.states: list[SchedulingState] = []

    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        self.states.append(state)
        return self._decisions_by_minute.get(state.current_time_min, ())


def _truck_id(job_id: str) -> str:
    return "T" + job_id.removeprefix("J")


def _scenario(
    arrivals: dict[str, int], dock_ids: tuple[str, ...] = ("D01",)
) -> ScenarioDefinition:
    """Each job belongs to its own single-job truck arriving at the given minute."""
    return ScenarioDefinition(
        plan=PlanSnapshot(
            trucks=tuple(
                TruckPlan(
                    _truck_id(job_id),
                    0,
                    False,
                    (JobPlan(job_id, OperationType.UNLOAD, "A", SERVICE_TIME_MIN),),
                )
                for job_id in arrivals
            )
        ),
        realization=RealizationDefinition(
            trucks=tuple(
                TruckRealization(_truck_id(job_id), arrival_min)
                for job_id, arrival_min in arrivals.items()
            ),
            jobs=tuple(JobRealization(job_id, SERVICE_TIME_MIN) for job_id in arrivals),
        ),
        docks=tuple(DockDefinition(dock_id) for dock_id in dock_ids),
    )


def test_arriving_job_is_served_on_a_free_dock_for_its_actual_service_time():
    simulation = WarehouseSimulation(_scenario({"J001": 495}), FCFSScheduler())

    simulation.run()

    assert simulation.event_log.records == (
        EventRecord(495, EventType.JOB_ARRIVAL, "J001", None),
        EventRecord(495, EventType.SERVICE_START, "J001", "D01"),
        EventRecord(525, EventType.SERVICE_END, "J001", "D01"),
    )


def test_waiting_job_starts_when_a_dock_becomes_free():
    simulation = WarehouseSimulation(
        _scenario({"J001": 470, "J002": 480}), FCFSScheduler()
    )

    simulation.run()

    job = simulation.runtime.jobs["J002"]
    assert (job.observed_arrival_min, job.service_start_min) == (480, 500)


def test_events_in_the_same_minute_form_one_decision_point():
    scheduler = _ScriptedScheduler({470: (Assign("J001", "D01"),)})
    simulation = WarehouseSimulation(
        _scenario({"J001": 470, "J002": 500, "J003": 500}), scheduler
    )

    simulation.run(until_min=501)

    # J001 ends and two jobs arrive at 500, still just one scheduler call
    assert [state.current_time_min for state in scheduler.states] == [470, 500]
    state_at_500 = scheduler.states[1]
    assert {job.job_id for job in state_at_500.waiting_jobs} == {"J002", "J003"}
    assert [dock.dock_id for dock in state_at_500.free_docks] == ["D01"]


def test_invalid_assignment_batch_is_rejected_without_starting_any_job():
    simulation = WarehouseSimulation(
        _scenario({"J001": 500, "J002": 500}, dock_ids=("D01", "D02")),
        _ScriptedScheduler({500: (Assign("J001", "D01"), Assign("J002", "D01"))}),
    )

    with pytest.raises(InvalidDecisionError, match="'D01'"):
        simulation.run()

    assert {job.status for job in simulation.runtime.jobs.values()} == {
        JobStatus.WAITING
    }


def test_arrivals_at_or_after_cutoff_are_ignored():
    simulation = WarehouseSimulation(
        _scenario({"J001": 0, "J002": 1439, "J003": 1440, "J004": 1500}),
        FCFSScheduler(),
    )

    simulation.run()

    assert set(simulation.runtime.jobs) == {"J001", "J002"}
    assert simulation.runtime.jobs["J002"].service_end_min == 1469
