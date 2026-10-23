from pathlib import Path

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

DATA_DIR = Path(__file__).resolve().parent / "data"
DOCKS = (DockDefinition("D01"), DockDefinition("D02"))
RELOCATION_TIME_MIN = 5


def main() -> None:
    scenario = load_scenario(
        DATA_DIR / "plan_trucks.csv",
        DATA_DIR / "plan_jobs.csv",
        DATA_DIR / "realization.csv",
        DOCKS,
        RELOCATION_TIME_MIN,
    )
    simulation = WarehouseSimulation(scenario, FCFSScheduler())
    simulation.run()

    print("Events")
    for record in simulation.event_log.records:
        line = f"{record.time_min:>4}  {record.event_type.value:<16}  {record.truck_id}"
        if record.job_id is not None:
            line += f"  {record.job_id}  {record.dock_id}"
        print(line)

    # waited = eligible until assigned to a dock, relocation not counted
    print("\nJobs")
    print("job   truck  dock  eligible  assigned  start  end  waited")
    for job in simulation.runtime.jobs.values():
        print(
            f"{job.job_id}  {job.truck_id}    {job.assigned_dock_id}   "
            f"{job.eligible_since_min:>8}  {job.assigned_min:>8}  "
            f"{job.service_start_min:>5}  {job.service_end_min:>3}  "
            f"{job.assigned_min - job.eligible_since_min:>6}"
        )

    print("\nTrucks")
    for truck in simulation.runtime.trucks.values():
        print(
            f"{truck.truck_id}  arrived {truck.observed_arrival_min}  "
            f"completed {truck.completed_min}"
        )


if __name__ == "__main__":
    main()
