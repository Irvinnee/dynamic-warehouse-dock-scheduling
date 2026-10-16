from pathlib import Path

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "examples" / "fcfs"


def main() -> None:
    scenario = load_scenario(
        DATA_DIR / "plan.csv",
        DATA_DIR / "realization.csv",
        (DockDefinition("D01"), DockDefinition("D02")),
    )
    simulation = WarehouseSimulation(scenario, FCFSScheduler())
    simulation.run()

    print("Events")
    for record in simulation.event_log.records:
        line = f"{record.time_min:<4} {record.event_type.value:<14} {record.job_id}"
        if record.dock_id is not None:
            line += f"  {record.dock_id}"
        print(line)

    print("\nJobs")
    for job in simulation.runtime.jobs.values():
        waited_min = job.service_start_min - job.observed_arrival_min
        print(
            f"{job.job_id}  {job.status.value}  "
            f"arrived {job.observed_arrival_min}  "
            f"started {job.service_start_min}  "
            f"ended {job.service_end_min}  "
            f"waited {waited_min:<2}  "
            f"dock {job.assigned_dock_id}"
        )

    print("\nDocks")
    for dock in simulation.runtime.docks.values():
        print(f"{dock.dock_id}  {dock.status.value}")


if __name__ == "__main__":
    main()
