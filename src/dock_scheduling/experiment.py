from dataclasses import dataclass

from dock_scheduling.domain import DockDefinition, ScenarioDefinition
from dock_scheduling.metrics import SimulationMetrics, calculate_metrics
from dock_scheduling.plan_generator import PlanGeneratorConfig, generate_plan
from dock_scheduling.realization_generator import (
    RealizationGeneratorConfig,
    generate_realization,
)
from dock_scheduling.scenario_validation import validate_scenario
from dock_scheduling.scheduler import Scheduler
from dock_scheduling.simulation import WarehouseSimulation


@dataclass(frozen=True)
class ExperimentResult:
    metrics: SimulationMetrics
    plan_seed: int
    realization_seed: int
    num_planned_trucks: int
    num_no_shows: int
    num_walk_ins: int


def run_experiment(
    plan_config: PlanGeneratorConfig,
    realization_config: RealizationGeneratorConfig,
    num_docks: int,
    relocation_time_min: int,
    plan_seed: int,
    realization_seed: int,
    scheduler: Scheduler,
) -> ExperimentResult:
    plan = generate_plan(plan_config, plan_seed)
    realization = generate_realization(plan, realization_config, realization_seed)
    scenario = ScenarioDefinition(
        plan=plan,
        realization=realization,
        docks=tuple(DockDefinition(f"D{i:02d}") for i in range(1, num_docks + 1)),
        relocation_time_min=relocation_time_min,
    )
    validate_scenario(scenario)
    simulation = WarehouseSimulation(scenario, scheduler)
    simulation.run()
    return ExperimentResult(
        metrics=calculate_metrics(simulation.runtime),
        plan_seed=plan_seed,
        realization_seed=realization_seed,
        num_planned_trucks=len(plan.trucks),
        num_no_shows=sum(
            truck.actual_arrival_min is None for truck in realization.trucks
        ),
        num_walk_ins=len(realization.unplanned_trucks),
    )
