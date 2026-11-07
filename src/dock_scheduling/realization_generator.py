import random
from dataclasses import dataclass, replace

from dock_scheduling.domain import (
    MINUTES_PER_DAY,
    JobPlan,
    JobRealization,
    PlanSnapshot,
    RealizationDefinition,
    TruckRealization,
    UnplannedTruck,
)


@dataclass(frozen=True)
class RealizationGeneratorConfig:
    arrival_std_min: float = 20.0
    no_show_probability: float = 0.0
    # lognormal factor on service times, mean stays at 1
    service_factor_sigma: float = 0.0
    num_unplanned_trucks: int = 0

    def __post_init__(self) -> None:
        if self.arrival_std_min < 0:
            raise ValueError(
                f"arrival_std_min must be >= 0, got {self.arrival_std_min}"
            )
        if not 0 <= self.no_show_probability <= 1:
            raise ValueError(
                f"no_show_probability must be in [0, 1], got {self.no_show_probability}"
            )
        if self.service_factor_sigma < 0:
            raise ValueError(
                f"service_factor_sigma must be >= 0, got {self.service_factor_sigma}"
            )
        if self.num_unplanned_trucks < 0:
            raise ValueError(
                f"num_unplanned_trucks must be >= 0, got {self.num_unplanned_trucks}"
            )


def generate_realization(
    plan: PlanSnapshot, config: RealizationGeneratorConfig, seed: int
) -> RealizationDefinition:
    # otherwise the resampling below could loop forever
    for truck in plan.trucks:
        if not 0 <= truck.planned_arrival_min < MINUTES_PER_DAY:
            raise ValueError(
                f"truck {truck.truck_id!r}: planned_arrival_min must be in "
                f"[0, {MINUTES_PER_DAY}), got {truck.planned_arrival_min}"
            )
    if config.num_unplanned_trucks > 0 and not plan.trucks:
        raise ValueError("walk-ins need a non-empty plan to copy jobs from")

    rng = random.Random(seed)
    trucks = []
    jobs = []
    for truck in plan.trucks:
        while True:
            arrival_min = truck.planned_arrival_min + round(
                rng.gauss(0.0, config.arrival_std_min)
            )
            if 0 <= arrival_min < MINUTES_PER_DAY:
                break
        is_no_show = rng.random() < config.no_show_probability
        trucks.append(
            TruckRealization(truck.truck_id, None if is_no_show else arrival_min)
        )
        for job in truck.jobs:
            jobs.append(_realize_job(rng, job, config.service_factor_sigma))

    # drawn last so adding walk-ins doesn't change the planned trucks
    unplanned_trucks = []
    planned_arrivals = [truck.planned_arrival_min for truck in plan.trucks]
    walk_in_job_count = 0
    for number in range(1, config.num_unplanned_trucks + 1):
        template = rng.choice(plan.trucks)
        arrival_min = rng.randint(min(planned_arrivals), max(planned_arrivals))
        walk_in_jobs = []
        for job in template.jobs:
            walk_in_job_count += 1
            walk_in_job = replace(job, job_id=f"WJ{walk_in_job_count:04d}")
            walk_in_jobs.append(walk_in_job)
            jobs.append(_realize_job(rng, walk_in_job, config.service_factor_sigma))
        unplanned_trucks.append(
            UnplannedTruck(f"W{number:03d}", arrival_min, tuple(walk_in_jobs))
        )

    _check_walk_in_ids_are_new(plan, unplanned_trucks)
    return RealizationDefinition(
        trucks=tuple(trucks),
        jobs=tuple(jobs),
        unplanned_trucks=tuple(unplanned_trucks),
    )


def _realize_job(rng: random.Random, job: JobPlan, sigma: float) -> JobRealization:
    factor = rng.lognormvariate(-(sigma**2) / 2, sigma)
    return JobRealization(
        job.job_id, max(1, round(job.estimated_service_time_min * factor))
    )


def _check_walk_in_ids_are_new(
    plan: PlanSnapshot, unplanned_trucks: list[UnplannedTruck]
) -> None:
    planned_ids = {truck.truck_id for truck in plan.trucks} | {
        job.job_id for truck in plan.trucks for job in truck.jobs
    }
    for walk_in in unplanned_trucks:
        for id_ in (walk_in.truck_id, *(job.job_id for job in walk_in.jobs)):
            if id_ in planned_ids:
                raise ValueError(f"walk-in id {id_!r} is already used in the plan")
