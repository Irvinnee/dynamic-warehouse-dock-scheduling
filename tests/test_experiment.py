from functools import partial

from dock_scheduling.experiment import ExperimentResult, run_experiment
from dock_scheduling.plan_generator import PlanGeneratorConfig
from dock_scheduling.realization_generator import RealizationGeneratorConfig
from dock_scheduling.scheduler import FCFSScheduler


def test_run_experiment_is_reproducible_and_returns_metrics():
    run = partial(
        run_experiment,
        PlanGeneratorConfig(num_trucks=10),
        RealizationGeneratorConfig(
            no_show_probability=0.2, service_factor_sigma=0.3, num_unplanned_trucks=2
        ),
        num_docks=2,
        relocation_time_min=5,
        plan_seed=1,
    )

    result = run(realization_seed=2, scheduler=FCFSScheduler())

    assert isinstance(result, ExperimentResult)
    assert (result.plan_seed, result.realization_seed) == (1, 2)
    assert (result.num_planned_trucks, result.num_walk_ins) == (10, 2)
    metrics = result.metrics
    assert 0 <= metrics.mean_job_waiting_time_min <= metrics.max_job_waiting_time_min
    assert 0 < metrics.mean_truck_turnaround_time_min <= metrics.makespan_min
    assert metrics.total_relocation_time_min >= 0

    assert run(realization_seed=2, scheduler=FCFSScheduler()) == result
    assert run(realization_seed=3, scheduler=FCFSScheduler()) != result
