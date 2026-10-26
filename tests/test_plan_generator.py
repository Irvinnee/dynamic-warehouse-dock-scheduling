from dataclasses import replace

import pytest

from dock_scheduling.plan_generator import (
    ArrivalProfile,
    PlanGeneratorConfig,
    generate_plan,
)
from dock_scheduling.scenario_validation import validate_plan

# 720 min window: 30 trucks -> 24 min intervals, 60 trucks -> 12 min
CONFIG = PlanGeneratorConfig(
    num_trucks=30,
    min_jobs_per_truck=1,
    max_jobs_per_truck=3,
    arrival_start_min=360,
    arrival_end_min=1080,
    peak_start_min=480,
    peak_end_min=600,
    peak_share=0.5,
    shortest_service_time_min=20,
    longest_service_time_min=90,
    load_probability=0.5,
    sections=("A", "B", "C"),
)


@pytest.mark.parametrize("profile", list(ArrivalProfile), ids=lambda p: p.name)
def test_same_seed_reproduces_plan_and_generated_plan_is_valid(profile):
    config = replace(CONFIG, arrival_profile=profile)

    plan = generate_plan(config, seed=7)

    assert generate_plan(config, seed=7) == plan
    assert generate_plan(config, seed=8) != plan
    validate_plan(plan)

    trucks = plan.trucks
    jobs = [job for truck in trucks for job in truck.jobs]
    assert [truck.truck_id for truck in trucks] == [f"T{i:03d}" for i in range(1, 31)]
    assert [job.job_id for job in jobs] == [
        f"J{i:04d}" for i in range(1, len(jobs) + 1)
    ]
    arrivals = [truck.planned_arrival_min for truck in trucks]
    assert arrivals == sorted(arrivals)
    assert all(360 <= arrival < 1080 for arrival in arrivals)
    assert all(1 <= len(truck.jobs) <= 3 for truck in trucks)
    assert all(20 <= job.estimated_service_time_min <= 90 for job in jobs)
    assert {job.section for job in jobs} <= {"A", "B", "C"}
    assert not any(truck.priority for truck in trucks)


def test_balanced_arrivals_are_spread_across_window():
    for seed in range(5):
        plan = generate_plan(CONFIG, seed)

        # i-th earliest appointment lands in the i-th 24 min interval
        intervals = [(truck.planned_arrival_min - 360) // 24 for truck in plan.trucks]
        assert intervals == list(range(30))


def test_peaked_arrivals_concentrate_appointments():
    config = replace(CONFIG, num_trucks=60)
    peaked = replace(config, arrival_profile=ArrivalProfile.PEAKED)

    def count_in_peak(plan) -> int:
        return sum(480 <= truck.planned_arrival_min < 600 for truck in plan.trucks)

    for seed in range(5):
        # BALANCED: 10 of the 12 min intervals fall into the 120 min peak
        assert count_in_peak(generate_plan(config, seed)) == 10
        # PEAKED: 30 in the peak, plus 5 of the other 30 spread over
        # 24 min intervals of the whole window
        assert count_in_peak(generate_plan(peaked, seed)) == 35


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"min_jobs_per_truck": 3, "max_jobs_per_truck": 2}, "jobs per truck"),
        ({"arrival_start_min": 600, "arrival_end_min": 600}, "arrival window"),
        ({"sections": ()}, "sections"),
        (
            {"arrival_profile": ArrivalProfile.PEAKED, "peak_end_min": 1200},
            "peak window",
        ),
    ],
    ids=["jobs_min_above_max", "empty_window", "no_sections", "peak_outside_window"],
)
def test_invalid_generator_config_is_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        replace(CONFIG, **overrides)
