import random
from dataclasses import dataclass
from enum import Enum

from dock_scheduling.domain import (
    MINUTES_PER_DAY,
    JobPlan,
    OperationType,
    PlanSnapshot,
    TruckPlan,
)


class ArrivalProfile(Enum):
    BALANCED = "BALANCED"
    PEAKED = "PEAKED"


@dataclass(frozen=True)
class PlanGeneratorConfig:
    num_trucks: int = 60
    min_jobs_per_truck: int = 1
    max_jobs_per_truck: int = 3
    arrival_start_min: int = 360
    arrival_end_min: int = 1080
    arrival_profile: ArrivalProfile = ArrivalProfile.BALANCED
    # PEAKED only: peak_share of trucks go into the peak, the rest anywhere
    peak_start_min: int = 480
    peak_end_min: int = 600
    peak_share: float = 0.5
    shortest_service_time_min: int = 20
    longest_service_time_min: int = 90
    load_probability: float = 0.5
    sections: tuple[str, ...] = ("A", "B", "C")

    def __post_init__(self) -> None:
        if self.num_trucks < 1:
            raise ValueError(f"num_trucks must be >= 1, got {self.num_trucks}")
        if not 1 <= self.min_jobs_per_truck <= self.max_jobs_per_truck:
            raise ValueError(
                "jobs per truck must satisfy 1 <= min <= max, got "
                f"{self.min_jobs_per_truck}..{self.max_jobs_per_truck}"
            )
        if not 0 <= self.arrival_start_min < self.arrival_end_min <= MINUTES_PER_DAY:
            raise ValueError(
                f"arrival window must satisfy 0 <= start < end <= {MINUTES_PER_DAY}, "
                f"got [{self.arrival_start_min}, {self.arrival_end_min})"
            )
        if not 1 <= self.shortest_service_time_min <= self.longest_service_time_min:
            raise ValueError(
                "service time must satisfy 1 <= shortest <= longest, got "
                f"{self.shortest_service_time_min}..{self.longest_service_time_min}"
            )
        if not 0 <= self.load_probability <= 1:
            raise ValueError(
                f"load_probability must be in [0, 1], got {self.load_probability}"
            )
        if not self.sections or not all(section.strip() for section in self.sections):
            raise ValueError(f"sections must be non-empty names, got {self.sections}")
        if self.arrival_profile is ArrivalProfile.PEAKED:
            if not (
                self.arrival_start_min
                <= self.peak_start_min
                < self.peak_end_min
                <= self.arrival_end_min
            ):
                raise ValueError(
                    f"peak window [{self.peak_start_min}, {self.peak_end_min}) must "
                    "be non-empty and inside the arrival window"
                )
            if not 0 < self.peak_share <= 1:
                raise ValueError(f"peak_share must be in (0, 1], got {self.peak_share}")


def generate_plan(config: PlanGeneratorConfig, seed: int) -> PlanSnapshot:
    rng = random.Random(seed)
    arrivals = sorted(_planned_arrivals(rng, config))
    trucks = []
    job_count = 0
    for truck_number, planned_arrival_min in enumerate(arrivals, start=1):
        jobs = []
        for _ in range(
            rng.randint(config.min_jobs_per_truck, config.max_jobs_per_truck)
        ):
            job_count += 1
            operation = (
                OperationType.LOAD
                if rng.random() < config.load_probability
                else OperationType.UNLOAD
            )
            section = rng.choice(config.sections)
            service_time_min = rng.randint(
                config.shortest_service_time_min, config.longest_service_time_min
            )
            jobs.append(
                JobPlan(f"J{job_count:04d}", operation, section, service_time_min)
            )
        trucks.append(
            TruckPlan(f"T{truck_number:03d}", planned_arrival_min, False, tuple(jobs))
        )
    return PlanSnapshot(tuple(trucks))


def _planned_arrivals(rng: random.Random, config: PlanGeneratorConfig) -> list[int]:
    if config.arrival_profile is ArrivalProfile.BALANCED:
        return _spread(
            rng, config.num_trucks, config.arrival_start_min, config.arrival_end_min
        )
    peak_count = round(config.peak_share * config.num_trucks)
    peak = _spread(rng, peak_count, config.peak_start_min, config.peak_end_min)
    background = _spread(
        rng,
        config.num_trucks - peak_count,
        config.arrival_start_min,
        config.arrival_end_min,
    )
    return peak + background


def _spread(rng: random.Random, count: int, start_min: int, end_min: int) -> list[int]:
    """Split [start_min, end_min) into count equal intervals, one arrival in each."""
    length = end_min - start_min
    return [
        start_min + (i * length + rng.randrange(length)) // count for i in range(count)
    ]
