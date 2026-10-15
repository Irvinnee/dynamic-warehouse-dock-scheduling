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
)
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.runtime import DockRuntime, DockStatus, JobRuntime, JobStatus
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.scheduling_state import SchedulingState
from dock_scheduling.simulation import WarehouseSimulation

SERVICE_TIME_MIN = 30


class _RecordingFCFSScheduler:
    def __init__(self) -> None:
        self.states: list[SchedulingState] = []

    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        self.states.append(state)
        return FCFSScheduler().schedule(state)


class _ScriptedScheduler:
    def __init__(self, decisions: tuple[Assign, ...]) -> None:
        self._decisions = decisions

    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        return self._decisions


def _scenario(
    arrivals: dict[str, int], dock_ids: tuple[str, ...]
) -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=tuple(
                JobPlan(
                    job_id,
                    480,
                    OperationType.UNLOAD,
                    False,
                    SERVICE_TIME_MIN,
                    "A",
                    None,
                )
                for job_id in arrivals
            )
        ),
        realization=RealizationDefinition(
            jobs=tuple(
                JobRealization(job_id, actual_arrival_min, SERVICE_TIME_MIN)
                for job_id, actual_arrival_min in arrivals.items()
            )
        ),
        docks=tuple(DockDefinition(dock_id) for dock_id in dock_ids),
    )


def _service_starts(simulation: WarehouseSimulation) -> list[EventRecord]:
    return [
        record
        for record in simulation.event_log.records
        if record.event_type is EventType.SERVICE_START
    ]


def _waiting_job_ids(state: SchedulingState) -> set[str]:
    return {job.job_id for job in state.waiting_jobs}


def _free_dock_ids(state: SchedulingState) -> set[str]:
    return {dock.dock_id for dock in state.free_docks}


def test_arrival_starts_service_on_free_dock_at_arrival_minute():
    simulation = WarehouseSimulation(
        _scenario({"J001": 495}, ("D01",)), FCFSScheduler()
    )

    simulation.run(until_min=496)

    assert simulation.runtime.jobs["J001"] == JobRuntime(
        "J001", JobStatus.IN_SERVICE, 495, 495, None, "D01"
    )
    assert _service_starts(simulation) == [
        EventRecord(495, EventType.SERVICE_START, "J001", "D01")
    ]


def test_one_batch_fills_all_free_docks_at_the_same_minute():
    simulation = WarehouseSimulation(
        _scenario({"J003": 500, "J002": 500, "J001": 500}, ("D02", "D01")),
        FCFSScheduler(),
    )

    simulation.run(until_min=501)

    assert _service_starts(simulation) == [
        EventRecord(500, EventType.SERVICE_START, "J001", "D01"),
        EventRecord(500, EventType.SERVICE_START, "J002", "D02"),
    ]
    assert simulation.runtime.jobs["J003"].status is JobStatus.WAITING


def test_simultaneous_arrivals_form_one_decision_point():
    scheduler = _RecordingFCFSScheduler()
    simulation = WarehouseSimulation(
        _scenario({"J001": 500, "J002": 500}, ("D01",)), scheduler
    )

    simulation.run(until_min=501)

    assert [state.current_time_min for state in scheduler.states] == [500]
    assert _waiting_job_ids(scheduler.states[0]) == {"J001", "J002"}


def test_service_ends_and_arrivals_at_same_minute_form_one_decision_point():
    scheduler = _RecordingFCFSScheduler()
    simulation = WarehouseSimulation(
        _scenario({"J001": 470, "J002": 470, "J003": 500, "J004": 500}, ("D01", "D02")),
        scheduler,
    )

    simulation.run(until_min=501)

    assert [state.current_time_min for state in scheduler.states] == [470, 500]
    state_at_500 = scheduler.states[1]
    assert _waiting_job_ids(state_at_500) == {"J003", "J004"}
    assert _free_dock_ids(state_at_500) == {"D01", "D02"}


def test_service_end_alone_starts_waiting_job_on_freed_dock():
    simulation = WarehouseSimulation(
        _scenario({"J001": 470, "J002": 480}, ("D01",)), FCFSScheduler()
    )

    simulation.run(until_min=501)

    assert simulation.runtime.jobs["J002"] == JobRuntime(
        "J002", JobStatus.IN_SERVICE, 480, 500, None, "D01"
    )


@pytest.mark.parametrize(
    "decisions",
    [
        (Assign("J001", "D01"), Assign("J001", "D02")),
        (Assign("J001", "D01"), Assign("J002", "D01")),
    ],
    ids=["duplicate_job", "duplicate_dock"],
)
def test_invalid_batch_starts_no_service(decisions):
    simulation = WarehouseSimulation(
        _scenario({"J001": 500, "J002": 500}, ("D01", "D02")),
        _ScriptedScheduler(decisions),
    )

    with pytest.raises(InvalidDecisionError):
        simulation.run()

    assert _service_starts(simulation) == []
    assert {job.status for job in simulation.runtime.jobs.values()} == {
        JobStatus.WAITING
    }
    assert simulation.runtime.docks == {
        "D01": DockRuntime("D01", DockStatus.FREE, None),
        "D02": DockRuntime("D02", DockStatus.FREE, None),
    }


def test_decision_at_until_min_waits_for_next_run():
    scheduler = _RecordingFCFSScheduler()
    simulation = WarehouseSimulation(_scenario({"J001": 500}, ("D01",)), scheduler)

    simulation.run(until_min=500)

    assert simulation.runtime.jobs == {}
    assert scheduler.states == []

    simulation.run()

    assert [state.current_time_min for state in scheduler.states] == [500, 530]
    assert simulation.runtime.jobs["J001"].service_start_min == 500
