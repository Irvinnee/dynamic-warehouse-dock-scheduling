import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from dock_scheduling.csv_loader import load_scenario
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

DOCKS = (DockDefinition("D01"), DockDefinition("D02"))
TRUCKS_HEADER = "truck_id,planned_arrival_min,priority"
JOBS_HEADER = "job_id,truck_id,sequence,operation,section,estimated_service_time_min"
REALIZATION_HEADER = "truck_id,job_id,actual_arrival_min,actual_service_time_min"


def _load(
    tmp_path: Path,
    trucks: Sequence[str] = ("T01,480,false",),
    jobs: Sequence[str] = ("J001,T01,1,UNLOAD,A,30",),
    realization: Sequence[str] = ("T01,J001,495,30",),
    jobs_header: str = JOBS_HEADER,
    docks: tuple[DockDefinition, ...] = DOCKS,
    relocation_time_min: int = 0,
) -> ScenarioDefinition:
    files = []
    for name, header, rows in [
        ("plan_trucks.csv", TRUCKS_HEADER, trucks),
        ("plan_jobs.csv", jobs_header, jobs),
        ("realization.csv", REALIZATION_HEADER, realization),
    ]:
        path = tmp_path / name
        path.write_text("\n".join([header, *rows]) + "\n")
        files.append(path)
    return load_scenario(*files, docks, relocation_time_min)


def _assert_rejected(tmp_path: Path, message: str, **overrides) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        _load(tmp_path, **overrides)


def test_valid_files_build_trucks_with_jobs_in_sequence_order(tmp_path):
    scenario = _load(
        tmp_path,
        trucks=["T02,-120,true", "T01,480,false"],
        jobs=[
            "J003,T01,3,LOAD,C,40",
            "J010,T02,1,LOAD,B,15",
            "J001,T01,1,UNLOAD,A,30",
            "J002,T01,2,UNLOAD,B,20",
        ],
        realization=[
            "T01,J002,495,25",
            "T02,J010,90,15",
            "T01,J001,495,30",
            "T01,J003,495,45",
        ],
        relocation_time_min=5,
    )

    assert scenario == ScenarioDefinition(
        plan=PlanSnapshot(
            trucks=(
                TruckPlan(
                    "T02", -120, True, (JobPlan("J010", OperationType.LOAD, "B", 15),)
                ),
                TruckPlan(
                    "T01",
                    480,
                    False,
                    (
                        JobPlan("J001", OperationType.UNLOAD, "A", 30),
                        JobPlan("J002", OperationType.UNLOAD, "B", 20),
                        JobPlan("J003", OperationType.LOAD, "C", 40),
                    ),
                ),
            )
        ),
        realization=RealizationDefinition(
            trucks=(TruckRealization("T01", 495), TruckRealization("T02", 90)),
            jobs=(
                JobRealization("J002", 25),
                JobRealization("J010", 15),
                JobRealization("J001", 30),
                JobRealization("J003", 45),
            ),
        ),
        docks=DOCKS,
        relocation_time_min=5,
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"trucks": ["T01,480,True"]}, "invalid priority 'True'"),
        ({"realization": ["T01,J001,49.5,30"]}, "invalid actual_arrival_min '49.5'"),
        ({"jobs": ["J001,T01,1,load,A,30"]}, "invalid operation 'load'"),
        (
            {"jobs_header": JOBS_HEADER.replace("section", "load_section")},
            "plan_jobs.csv: expected columns",
        ),
    ],
    ids=["priority", "integer", "operation", "header"],
)
def test_malformed_csv_content_is_rejected(tmp_path, overrides, message):
    _assert_rejected(tmp_path, message, **overrides)


@pytest.mark.parametrize(
    ("jobs", "realization", "message"),
    [
        (
            ["J001,T01,1,UNLOAD,A,30", "J002,T09,1,LOAD,B,20"],
            ["T01,J001,495,30", "T09,J002,500,20"],
            "job 'J002' references unknown truck 'T09'",
        ),
        (
            ["J001,T01,1,UNLOAD,A,30", "J002,T01,1,LOAD,B,20"],
            ["T01,J001,495,30", "T01,J002,495,20"],
            "truck 'T01': job sequence must be 1..2",
        ),
        (
            ["J001,T01,1,UNLOAD,A,30", "J002,T01,3,LOAD,B,20"],
            ["T01,J001,495,30", "T01,J002,495,20"],
            "truck 'T01': job sequence must be 1..2",
        ),
    ],
    ids=["unknown_truck", "repeated_sequence", "sequence_gap"],
)
def test_invalid_job_reference_or_sequence_is_rejected(
    tmp_path, jobs, realization, message
):
    _assert_rejected(tmp_path, message, jobs=jobs, realization=realization)


@pytest.mark.parametrize(
    ("realization", "message"),
    [
        (
            ["T01,J001,495,30", "T01,J002,500,20", "T02,J101,500,30"],
            "differs from 495",
        ),
        (
            ["T01,J001,495,30", "T02,J002,500,20", "T02,J101,500,30"],
            "belongs to truck 'T01'",
        ),
        (["T01,J001,495,30", "T02,J101,500,30"], "job 'J002': no realization"),
    ],
    ids=["arrival_differs", "job_under_wrong_truck", "missing_job"],
)
def test_inconsistent_realization_is_rejected(tmp_path, realization, message):
    _assert_rejected(
        tmp_path,
        message,
        trucks=["T01,480,false", "T02,490,false"],
        jobs=[
            "J001,T01,1,UNLOAD,A,30",
            "J002,T01,2,LOAD,B,20",
            "J101,T02,1,LOAD,C,30",
        ],
        realization=realization,
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "trucks": ["T01,480,false", "T02,490,false"],
                "jobs": ["J001,T01,1,UNLOAD,A,30", "J001,T02,1,LOAD,B,20"],
                "realization": ["T01,J001,495,30", "T02,J001,500,20"],
            },
            "duplicate job_id 'J001'",
        ),
        (
            {"realization": ["T01,J001,495,0"]},
            "actual_service_time_min must be > 0",
        ),
        (
            {"realization": ["T01,J001,1440,30"]},
            "actual_arrival_min must be None or in [0, 1440)",
        ),
        ({"docks": ()}, "scenario has no docks"),
        ({"relocation_time_min": -1}, "relocation_time_min must be >= 0"),
    ],
    ids=[
        "duplicate_job_id",
        "zero_service_time",
        "arrival_at_1440",
        "no_docks",
        "negative_relocation",
    ],
)
def test_invalid_scenario_or_configuration_is_rejected(tmp_path, overrides, message):
    _assert_rejected(tmp_path, message, **overrides)
