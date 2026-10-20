from collections import Counter
from pathlib import Path

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

FCFS_EXAMPLE_DIR = Path(__file__).parent.parent / "data" / "examples" / "fcfs"
DOCKS = (DockDefinition("D01"), DockDefinition("D02"))

MULTI_JOB_PLAN_TRUCKS = """\
truck_id,planned_arrival_min,priority
T01,90,false
T02,100,false
T03,105,false
"""

MULTI_JOB_PLAN_JOBS = """\
job_id,truck_id,sequence,operation,section,estimated_service_time_min
J001,T01,1,UNLOAD,A,40
J002,T01,2,LOAD,B,20
J101,T02,1,UNLOAD,C,50
J201,T03,1,LOAD,A,40
"""

MULTI_JOB_REALIZATION = """\
truck_id,job_id,actual_arrival_min,actual_service_time_min
T01,J001,100,30
T01,J002,100,20
T02,J101,100,50
T03,J201,110,40
"""


def _run(directory: Path) -> WarehouseSimulation:
    scenario = load_scenario(
        directory / "plan_trucks.csv",
        directory / "plan_jobs.csv",
        directory / "realization.csv",
        DOCKS,
    )
    simulation = WarehouseSimulation(scenario, FCFSScheduler())
    simulation.run()
    return simulation


def _assert_events(
    simulation: WarehouseSimulation, expected: list[EventRecord]
) -> None:
    # same-minute events can come in any order, so compare as multisets
    records = simulation.event_log.records
    assert Counter(records) == Counter(expected)
    times = [record.time_min for record in records]
    assert times == sorted(times)


def test_example_csv_scenario_runs_to_completion_with_fcfs():
    simulation = _run(FCFS_EXAMPLE_DIR)

    _assert_events(
        simulation,
        [
            EventRecord(100, EventType.TRUCK_ARRIVAL, "T01", None, None),
            EventRecord(100, EventType.JOB_START, "T01", "J001", "D01"),
            EventRecord(110, EventType.TRUCK_ARRIVAL, "T02", None, None),
            EventRecord(110, EventType.JOB_START, "T02", "J002", "D02"),
            EventRecord(120, EventType.TRUCK_ARRIVAL, "T03", None, None),
            EventRecord(140, EventType.JOB_END, "T01", "J001", "D01"),
            EventRecord(140, EventType.JOB_START, "T03", "J003", "D01"),
            EventRecord(160, EventType.JOB_END, "T02", "J002", "D02"),
            EventRecord(160, EventType.JOB_END, "T03", "J003", "D01"),
        ],
    )
    assert {
        truck_id: truck.completed_min
        for truck_id, truck in simulation.runtime.trucks.items()
    } == {"T01": 140, "T02": 160, "T03": 160}


def test_multi_job_csv_scenario_with_waiting_between_jobs(tmp_path):
    (tmp_path / "plan_trucks.csv").write_text(MULTI_JOB_PLAN_TRUCKS)
    (tmp_path / "plan_jobs.csv").write_text(MULTI_JOB_PLAN_JOBS)
    (tmp_path / "realization.csv").write_text(MULTI_JOB_REALIZATION)

    simulation = _run(tmp_path)

    # at 130 D01 goes to J201 (waiting since 110), J002 has to wait for D02
    # until 150
    _assert_events(
        simulation,
        [
            EventRecord(100, EventType.TRUCK_ARRIVAL, "T01", None, None),
            EventRecord(100, EventType.TRUCK_ARRIVAL, "T02", None, None),
            EventRecord(100, EventType.JOB_START, "T01", "J001", "D01"),
            EventRecord(100, EventType.JOB_START, "T02", "J101", "D02"),
            EventRecord(110, EventType.TRUCK_ARRIVAL, "T03", None, None),
            EventRecord(130, EventType.JOB_END, "T01", "J001", "D01"),
            EventRecord(130, EventType.JOB_START, "T03", "J201", "D01"),
            EventRecord(150, EventType.JOB_END, "T02", "J101", "D02"),
            EventRecord(150, EventType.JOB_START, "T01", "J002", "D02"),
            EventRecord(170, EventType.JOB_END, "T03", "J201", "D01"),
            EventRecord(170, EventType.JOB_END, "T01", "J002", "D02"),
        ],
    )
    assert {
        truck_id: truck.completed_min
        for truck_id, truck in simulation.runtime.trucks.items()
    } == {"T01": 170, "T02": 150, "T03": 170}
