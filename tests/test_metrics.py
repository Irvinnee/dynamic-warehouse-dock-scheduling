import pytest

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
from dock_scheduling.metrics import SimulationMetrics, calculate_metrics
from dock_scheduling.scheduler import FCFSScheduler
from dock_scheduling.simulation import WarehouseSimulation

# truck_id -> (arrival, [(job_id, service time)]), estimates = actual times
TRUCKS = {
    "T01": (100, [("J001", 20), ("J002", 10)]),
    "T02": (100, [("J101", 40)]),
    "T03": (110, [("J201", 30)]),
}


def _scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        plan=PlanSnapshot(
            tuple(
                TruckPlan(
                    truck_id,
                    arrival_min,
                    False,
                    tuple(
                        JobPlan(job_id, OperationType.UNLOAD, "A", service_min)
                        for job_id, service_min in jobs
                    ),
                )
                for truck_id, (arrival_min, jobs) in TRUCKS.items()
            )
        ),
        realization=RealizationDefinition(
            trucks=tuple(
                TruckRealization(truck_id, arrival_min)
                for truck_id, (arrival_min, _) in TRUCKS.items()
            ),
            jobs=tuple(
                JobRealization(job_id, service_min)
                for _, jobs in TRUCKS.values()
                for job_id, service_min in jobs
            ),
        ),
        docks=(DockDefinition("D01"), DockDefinition("D02")),
        relocation_time_min=5,
    )


def test_metrics_for_known_simulation_result():
    simulation = WarehouseSimulation(_scenario(), FCFSScheduler())
    assert calculate_metrics(simulation.runtime) == SimulationMetrics(0.0, 0, 0.0, 0, 0)

    simulation.run(until_min=130)
    with pytest.raises(ValueError, match="unfinished"):
        calculate_metrics(simulation.runtime)
    simulation.run()

    # 100: J001 -> D01, J101 -> D02; 120: J201 (waiting since 110) gets D01
    # 140: J002 (waiting since 120) gets D02, relocates from D01, starts at 145
    # waits: J001 0, J101 0, J201 10, J002 20; ends: T01 155, T02 140, T03 150
    assert calculate_metrics(simulation.runtime) == SimulationMetrics(
        mean_job_waiting_time_min=7.5,
        max_job_waiting_time_min=20,
        mean_truck_turnaround_time_min=45.0,
        makespan_min=155,
        total_relocation_time_min=5,
    )
