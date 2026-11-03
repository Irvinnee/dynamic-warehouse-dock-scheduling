# Dynamic Warehouse Dock Scheduling

Engineering project on dynamic scheduling of truck jobs at warehouse docks. It simulates one warehouse day, so that different scheduling methods can be run on the same scenarios and compared.

## Problem

Trucks arrive during the day with one or more `LOAD` or `UNLOAD` jobs that have to be done in a fixed order. Each job needs a dock, and when no dock is free, the truck waits.

The plan says when trucks should arrive and how long their jobs should take. What actually happens differs from the plan and only becomes known during the day.

## Simulation model

The simulation separates the plan from the actual realization. Trucks may arrive early or late or not at all (no-shows), and service times may differ from the estimates. The jobs of a truck are processed in their predefined order, and moving to another dock between two jobs takes a fixed relocation time.

The scheduler is called whenever a truck arrives or a job ends. It sees only planned and already observed data, never the future realization. A truck that arrives does so between minute 0 and 1439 and is served to the end, even after midnight.

## FCFS baseline

The current scheduler is a first-come, first-served baseline. Jobs that have waited longest get the free docks first, and a truck keeps its previous dock when that dock is free.

## Input

A scenario can be read from three CSV files, with times in minutes from midnight:

```text
plan_trucks.csv   truck_id,planned_arrival_min,priority
plan_jobs.csv     job_id,truck_id,sequence,operation,section,estimated_service_time_min
realization.csv   truck_id,job_id,actual_arrival_min,actual_service_time_min
```

`examples/data/` contains a small scenario with three trucks and two docks, and `examples/run_fcfs.py` runs it with FCFS.

## Synthetic scenario generation

`generate_plan` creates a reproducible plan from a configuration and a seed. Appointments are either spread over the window (`BALANCED`) or concentrated in a peak (`PEAKED`). `generate_realization` then creates the actual day for that plan from its own seed: early and late arrivals, no-shows and service-time deviations.

```python
from dock_scheduling.plan_generator import PlanGeneratorConfig, generate_plan
from dock_scheduling.realization_generator import (
    RealizationGeneratorConfig,
    generate_realization,
)

plan = generate_plan(PlanGeneratorConfig(num_trucks=60), seed=1)
realization = generate_realization(
    plan, RealizationGeneratorConfig(no_show_probability=0.05), seed=2
)
```

## Running

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```text
uv sync
uv run python examples/run_fcfs.py
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Status

Implemented: the simulation model, CSV input, the FCFS baseline, plan generation and realization generation.
