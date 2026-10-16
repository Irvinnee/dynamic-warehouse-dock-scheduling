from pathlib import Path

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition
from dock_scheduling.event_log import EventRecord, EventType
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

FCFS_EXAMPLE_DIR = Path(__file__).parent.parent / "data" / "examples" / "fcfs"


def test_example_csv_scenario_runs_to_completion_with_fcfs():
    scenario = load_scenario(
        FCFS_EXAMPLE_DIR / "plan.csv",
        FCFS_EXAMPLE_DIR / "realization.csv",
        (DockDefinition("D01"), DockDefinition("D02")),
    )
    simulation = WarehouseSimulation(scenario, FCFSScheduler())

    simulation.run()

    # J003 arrives at 120 with both docks busy and gets D01 once J001 ends
    service_starts = [
        record
        for record in simulation.event_log.records
        if record.event_type is EventType.SERVICE_START
    ]
    assert service_starts == [
        EventRecord(100, EventType.SERVICE_START, "J001", "D01"),
        EventRecord(110, EventType.SERVICE_START, "J002", "D02"),
        EventRecord(140, EventType.SERVICE_START, "J003", "D01"),
    ]
    assert {
        job_id: job.service_end_min for job_id, job in simulation.runtime.jobs.items()
    } == {"J001": 140, "J002": 160, "J003": 160}
