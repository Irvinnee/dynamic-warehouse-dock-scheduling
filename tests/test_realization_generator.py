from dataclasses import replace

from dock_scheduling.domain import DockDefinition, PlanSnapshot, ScenarioDefinition
from dock_scheduling.plan_generator import PlanGeneratorConfig, generate_plan
from dock_scheduling.realization_generator import (
    RealizationGeneratorConfig,
    generate_realization,
)
from dock_scheduling.scenario_validation import validate_scenario

PLAN = generate_plan(PlanGeneratorConfig(num_trucks=20), seed=1)
PLANNED_JOBS = [job for truck in PLAN.trucks for job in truck.jobs]


def test_same_inputs_reproduce_valid_realization():
    config = RealizationGeneratorConfig(
        arrival_std_min=20.0, no_show_probability=0.2, service_factor_sigma=0.3
    )

    realization = generate_realization(PLAN, config, seed=7)

    assert generate_realization(PLAN, config, seed=7) == realization
    assert generate_realization(PLAN, config, seed=8) != realization
    prioritized = PlanSnapshot(
        tuple(replace(truck, priority=True) for truck in PLAN.trucks)
    )
    assert generate_realization(prioritized, config, seed=7) == realization

    assert [truck.truck_id for truck in realization.trucks] == [
        truck.truck_id for truck in PLAN.trucks
    ]
    assert [job.job_id for job in realization.jobs] == [
        job.job_id for job in PLANNED_JOBS
    ]
    validate_scenario(
        ScenarioDefinition(PLAN, realization, (DockDefinition("D01"),), 0)
    )


def test_zero_disturbance_reproduces_plan():
    config = RealizationGeneratorConfig(
        arrival_std_min=0.0, no_show_probability=0.0, service_factor_sigma=0.0
    )

    realization = generate_realization(PLAN, config, seed=7)

    assert [truck.actual_arrival_min for truck in realization.trucks] == [
        truck.planned_arrival_min for truck in PLAN.trucks
    ]
    assert [job.actual_service_time_min for job in realization.jobs] == [
        job.estimated_service_time_min for job in PLANNED_JOBS
    ]

    disturbed = generate_realization(
        PLAN, replace(config, service_factor_sigma=0.5), seed=7
    )
    actual = [job.actual_service_time_min for job in disturbed.jobs]
    assert all(service_time_min >= 1 for service_time_min in actual)
    assert actual != [job.estimated_service_time_min for job in PLANNED_JOBS]


def test_no_show_probability_controls_arrivals():
    def arrivals(no_show_probability: float) -> list[int | None]:
        config = RealizationGeneratorConfig(no_show_probability=no_show_probability)
        realization = generate_realization(PLAN, config, seed=7)
        assert len(realization.jobs) == len(PLANNED_JOBS)
        return [truck.actual_arrival_min for truck in realization.trucks]

    assert arrivals(1.0) == [None] * len(PLAN.trucks)
    assert None not in arrivals(0.0)
