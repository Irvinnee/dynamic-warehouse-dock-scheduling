from collections import Counter

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.runtime import DockRuntime, DockStatus, JobRuntime, JobStatus
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

PLAN_CSV = """\
job_id,planned_arrival_min,operation,priority,estimated_service_time_min,unload_section,load_section
J001,100,UNLOAD,false,40,A,
J002,110,LOAD,false,50,,B
J003,120,BOTH,false,20,A,B
"""

REALIZATION_CSV = """\
job_id,actual_arrival_min,actual_service_time_min
J001,100,40
J002,110,50
J003,120,20
"""


def _completed(
    job_id: str, arrival_min: int, start_min: int, end_min: int, dock_id: str
) -> JobRuntime:
    return JobRuntime(
        job_id=job_id,
        status=JobStatus.COMPLETED,
        observed_arrival_min=arrival_min,
        service_start_min=start_min,
        service_end_min=end_min,
        assigned_dock_id=dock_id,
    )


def test_csv_scenario_runs_to_completion_with_fcfs(tmp_path):
    plan_path = tmp_path / "plan.csv"
    realization_path = tmp_path / "realization.csv"
    plan_path.write_text(PLAN_CSV)
    realization_path.write_text(REALIZATION_CSV)
    scenario = load_scenario(
        plan_path,
        realization_path,
        (DockDefinition("D01"), DockDefinition("D02")),
    )
    simulation = WarehouseSimulation(scenario, FCFSScheduler())

    simulation.run()

    assert simulation.runtime.jobs == {
        "J001": _completed("J001", 100, 100, 140, "D01"),
        "J002": _completed("J002", 110, 110, 160, "D02"),
        "J003": _completed("J003", 120, 140, 160, "D01"),
    }
    assert simulation.runtime.docks == {
        "D01": DockRuntime("D01", DockStatus.FREE, None),
        "D02": DockRuntime("D02", DockStatus.FREE, None),
    }
    records = simulation.event_log.records
    assert Counter(records) == Counter(
        [
            EventRecord(100, EventType.JOB_ARRIVAL, "J001", None),
            EventRecord(100, EventType.SERVICE_START, "J001", "D01"),
            EventRecord(110, EventType.JOB_ARRIVAL, "J002", None),
            EventRecord(110, EventType.SERVICE_START, "J002", "D02"),
            EventRecord(120, EventType.JOB_ARRIVAL, "J003", None),
            EventRecord(140, EventType.SERVICE_END, "J001", "D01"),
            EventRecord(140, EventType.SERVICE_START, "J003", "D01"),
            EventRecord(160, EventType.SERVICE_END, "J002", "D02"),
            EventRecord(160, EventType.SERVICE_END, "J003", "D01"),
        ]
    )
    times = [record.time_min for record in records]
    assert times == sorted(times)
