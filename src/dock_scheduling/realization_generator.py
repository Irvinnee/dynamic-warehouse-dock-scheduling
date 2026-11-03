import random
from dataclasses import dataclass

from dock_scheduling.domain import (
    MINUTES_PER_DAY,
    JobRealization,
    PlanSnapshot,
    RealizationDefinition,
    TruckRealization,
)


@dataclass(frozen=True)
class RealizationGeneratorConfig:
    arrival_std_min: float = 20.0
    no_show_probability: float = 0.0
    # lognormal factor on service times, mean stays at 1
    service_factor_sigma: float = 0.0

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

    rng = random.Random(seed)
    sigma = config.service_factor_sigma
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
            factor = rng.lognormvariate(-(sigma**2) / 2, sigma)
            jobs.append(
                JobRealization(
                    job.job_id,
                    max(1, round(job.estimated_service_time_min * factor)),
                )
            )
    return RealizationDefinition(trucks=tuple(trucks), jobs=tuple(jobs))
