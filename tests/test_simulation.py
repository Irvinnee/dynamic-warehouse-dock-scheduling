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

ESTIMATED_SERVICE_TIME_MIN = 30


class _ScriptedScheduler:
    def __init__(self, decisions_by_minute: dict[int, tuple[Assign, ...]]) -> None:
        self._decisions_by_minute = decisions_by_minute
        self.states: list[SchedulingState] = []

    def schedule(self, state: SchedulingState) -> tuple[Assign, ...]:
        self.states.append(state)
        return self._decisions_by_minute.get(state.current_time_min, ())


def _scenario(
    trucks: dict[str, tuple[int | None, list[tuple[str, int]]]],
    dock_ids: tuple[str, ...] = ("D01",),
    relocation_time_min: int = 0,
) -> ScenarioDefinition:
    """trucks maps truck_id to (actual arrival, [(job_id, actual service time)])."""
    return ScenarioDefinition(
        plan=PlanSnapshot(
            trucks=tuple(
                TruckPlan(
                    truck_id,
                    0,
                    False,
                    tuple(
                        JobPlan(
                            job_id,
                            OperationType.UNLOAD,
                            "A",
                            ESTIMATED_SERVICE_TIME_MIN,
                        )
                        for job_id, _ in jobs
                    ),
                )
                for truck_id, (_, jobs) in trucks.items()
            )
        ),
        realization=RealizationDefinition(
            trucks=tuple(
                TruckRealization(truck_id, arrival_min)
                for truck_id, (arrival_min, _) in trucks.items()
            ),
            jobs=tuple(
                JobRealization(job_id, service_min)
                for _, jobs in trucks.values()
                for job_id, service_min in jobs
            ),
        ),
        docks=tuple(DockDefinition(dock_id) for dock_id in dock_ids),
        relocation_time_min=relocation_time_min,
    )


def _timeline(simulation: WarehouseSimulation, job_id: str) -> tuple:
    job = simulation.runtime.jobs[job_id]
    return (job.eligible_since_min, job.service_start_min, job.service_end_min)


THREE_JOB_TRUCK = {"T01": (100, [("J001", 20), ("J002", 15), ("J003", 10)])}


def test_truck_arrival_activates_only_its_first_job():
    scheduler = _ScriptedScheduler({})
    simulation = WarehouseSimulation(
        _scenario({**THREE_JOB_TRUCK, "T02": (300, [("J101", 10)])}), scheduler
    )

    simulation.run(until_min=101)

    assert set(simulation.runtime.jobs) == {"J001"}
    # scheduler sees the estimate, not the actual 20 min, and nothing
    # about the truck that hasn't arrived yet
    assert [
        (job.job_id, job.eligible_since_min, job.estimated_service_time_min)
        for job in scheduler.states[0].eligible_jobs
    ] == [("J001", 100, ESTIMATED_SERVICE_TIME_MIN)]


def test_ordered_jobs_run_sequentially_and_later_job_cannot_start_early():
    simulation = WarehouseSimulation(_scenario(THREE_JOB_TRUCK), FCFSScheduler())

    simulation.run()

    assert simulation.event_log.records == (
        EventRecord(100, EventType.TRUCK_ARRIVAL, "T01", None, None),
        EventRecord(100, EventType.JOB_START, "T01", "J001", "D01"),
        EventRecord(120, EventType.JOB_END, "T01", "J001", "D01"),
        EventRecord(120, EventType.JOB_START, "T01", "J002", "D01"),
        EventRecord(135, EventType.JOB_END, "T01", "J002", "D01"),
        EventRecord(135, EventType.JOB_START, "T01", "J003", "D01"),
        EventRecord(145, EventType.JOB_END, "T01", "J003", "D01"),
    )
    assert simulation.runtime.trucks["T01"].completed_min == 145

    # T02 arriving is a decision point even though J001 is still in service
    early = WarehouseSimulation(
        _scenario(
            {**THREE_JOB_TRUCK, "T02": (110, [("J101", 10)])}, dock_ids=("D01", "D02")
        ),
        _ScriptedScheduler(
            {100: (Assign("J001", "D01"),), 110: (Assign("J002", "D02"),)}
        ),
    )

    with pytest.raises(InvalidDecisionError, match="'J002'"):
        early.run()


def test_truck_waits_for_a_free_dock():
    simulation = WarehouseSimulation(
        _scenario(
            {
                "T01": (100, [("J001", 20), ("J002", 10)]),
                "T02": (110, [("J101", 30)]),
            }
        ),
        FCFSScheduler(),
    )

    simulation.run()

    # J101 has waited since 110 so it beats J002 (eligible only at 120) to D01,
    # then J002 waits until J101 is done
    assert _timeline(simulation, "J101") == (110, 120, 150)
    assert _timeline(simulation, "J002") == (120, 150, 160)
    assert simulation.runtime.trucks["T01"].completed_min == 160


def test_trucks_progress_through_their_jobs_independently():
    simulation = WarehouseSimulation(
        _scenario(
            {
                "T01": (100, [("J001", 20), ("J002", 20)]),
                "T02": (100, [("J101", 5), ("J102", 5), ("J103", 5)]),
            },
            dock_ids=("D01", "D02"),
        ),
        FCFSScheduler(),
    )

    simulation.run()

    assert [_timeline(simulation, job_id) for job_id in ("J101", "J102", "J103")] == [
        (100, 100, 105),
        (105, 105, 110),
        (110, 110, 115),
    ]
    assert simulation.runtime.trucks["T02"].completed_min == 115
    assert simulation.runtime.trucks["T01"].completed_min == 140


def test_events_in_the_same_minute_form_one_decision_point():
    scheduler = _ScriptedScheduler({100: (Assign("J001", "D01"),)})
    simulation = WarehouseSimulation(
        _scenario(
            {
                "T01": (100, [("J001", 20), ("J002", 10)]),
                "T02": (120, [("J101", 10)]),
                "T03": (120, [("J201", 10)]),
            }
        ),
        scheduler,
    )

    simulation.run(until_min=121)

    # J001 ends and two trucks arrive at 120, still just one scheduler call
    assert [state.current_time_min for state in scheduler.states] == [100, 120]
    state_at_120 = scheduler.states[1]
    assert {job.job_id for job in state_at_120.eligible_jobs} == {
        "J002",
        "J101",
        "J201",
    }
    assert [dock.dock_id for dock in state_at_120.free_docks] == ["D01"]


def test_invalid_assignment_batch_is_rejected_without_starting_any_job():
    simulation = WarehouseSimulation(
        _scenario(
            {"T01": (500, [("J001", 30)]), "T02": (500, [("J002", 30)])},
            dock_ids=("D01", "D02"),
        ),
        _ScriptedScheduler({500: (Assign("J001", "D01"), Assign("J002", "D01"))}),
    )

    with pytest.raises(InvalidDecisionError, match="'D01'"):
        simulation.run()

    assert {job.status for job in simulation.runtime.jobs.values()} == {
        JobStatus.WAITING
    }
    assert EventType.JOB_START not in {
        record.event_type for record in simulation.event_log.records
    }


@pytest.mark.parametrize(
    ("second_dock_id", "expected_start_min", "expected_relocation_starts"),
    [("D01", 120, []), ("D02", 125, [120])],
    ids=["same_dock", "other_dock"],
)
def test_relocation_time_is_added_only_when_the_dock_changes(
    second_dock_id, expected_start_min, expected_relocation_starts
):
    simulation = WarehouseSimulation(
        _scenario(
            {"T01": (100, [("J001", 20), ("J002", 10)])},
            dock_ids=("D01", "D02"),
            relocation_time_min=5,
        ),
        _ScriptedScheduler(
            {100: (Assign("J001", "D01"),), 120: (Assign("J002", second_dock_id),)}
        ),
    )

    simulation.run()

    assert _timeline(simulation, "J002") == (
        120,
        expected_start_min,
        expected_start_min + 10,
    )
    assert [
        record.time_min
        for record in simulation.event_log.records
        if record.event_type is EventType.RELOCATION_START
    ] == expected_relocation_starts


def test_relocation_reserves_the_destination_dock():
    scheduler = _ScriptedScheduler(
        {
            100: (Assign("J001", "D01"),),
            120: (Assign("J002", "D02"), Assign("J101", "D01")),
            122: (Assign("J201", "D02"),),
        }
    )
    simulation = WarehouseSimulation(
        _scenario(
            {
                "T01": (100, [("J001", 20), ("J002", 10)]),
                "T02": (120, [("J101", 30)]),
                "T03": (122, [("J201", 30)]),
            },
            dock_ids=("D01", "D02"),
            relocation_time_min=5,
        ),
        scheduler,
    )

    simulation.run(until_min=122)

    # J002 is still relocating to D02 and someone else already took the dock it
    # left, so at 122 nothing is free for J201 and taking D02 gets rejected
    assert simulation.runtime.jobs["J002"].status is JobStatus.RELOCATING
    assert simulation.runtime.jobs["J101"].status is JobStatus.IN_SERVICE
    with pytest.raises(InvalidDecisionError, match="'D02'"):
        simulation.run()
    state_at_122 = scheduler.states[-1]
    assert state_at_122.current_time_min == 122
    assert state_at_122.free_docks == ()


def test_no_show_never_arrives_and_arrival_at_1439_finishes_after_midnight():
    simulation = WarehouseSimulation(
        _scenario(
            {
                "T00": (0, [("J000", 10)]),
                "T01": (1439, [("J001", 20), ("J002", 30)]),
                "T02": (None, [("J101", 10)]),
            }
        ),
        FCFSScheduler(),
    )

    simulation.run()

    assert set(simulation.runtime.trucks) == {"T00", "T01"}
    assert "J101" not in simulation.runtime.jobs
    assert _timeline(simulation, "J002") == (1459, 1459, 1489)
    assert simulation.runtime.trucks["T01"].completed_min == 1489
    assert {record.truck_id for record in simulation.event_log.records} == {
        "T00",
        "T01",
    }
