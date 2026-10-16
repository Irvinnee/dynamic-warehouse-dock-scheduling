import re
from pathlib import Path

import pytest

from dock_scheduling.csv_loader import load_scenario
from dock_scheduling.domain import DockDefinition, OperationType

EXAMPLES_DIR = Path(__file__).parent.parent / "data" / "examples" / "validation"
DOCKS = (DockDefinition("D01"), DockDefinition("D02"))
PLAN_HEADER = (
    "job_id,planned_arrival_min,operation,priority,"
    "estimated_service_time_min,unload_section,load_section"
)
REALIZATION_HEADER = "job_id,actual_arrival_min,actual_service_time_min"


def _assert_rejected(
    tmp_path: Path, plan_rows: list[str], realization_rows: list[str], message: str
) -> None:
    plan_path = tmp_path / "plan.csv"
    realization_path = tmp_path / "realization.csv"
    plan_path.write_text("\n".join([PLAN_HEADER, *plan_rows]) + "\n")
    realization_path.write_text(
        "\n".join([REALIZATION_HEADER, *realization_rows]) + "\n"
    )

    with pytest.raises(ValueError, match=re.escape(message)):
        load_scenario(plan_path, realization_path, DOCKS)


def test_example_files_load_as_valid_scenario():
    scenario = load_scenario(
        EXAMPLES_DIR / "plan.csv", EXAMPLES_DIR / "realization.csv", DOCKS
    )

    assert [job.job_id for job in scenario.plan.jobs] == [
        "J001",
        "J002",
        "J003",
        "J004",
    ]
    assert scenario.plan.jobs[2].operation is OperationType.BOTH
    assert scenario.realization.jobs[3].actual_arrival_min == 1450


@pytest.mark.parametrize(
    ("plan_row", "realization_row", "message"),
    [
        ("J001,480,UNLOAD,yes,30,A,", "J001,495,30", "field 'priority'"),
        ("J001,480,UNLOAD,false,30,A,", "J001,49.5,30", "field 'actual_arrival_min'"),
    ],
    ids=["priority", "integer"],
)
def test_malformed_csv_value_is_rejected(tmp_path, plan_row, realization_row, message):
    _assert_rejected(tmp_path, [plan_row], [realization_row], message)


@pytest.mark.parametrize(
    ("plan_rows", "realization_rows", "message"),
    [
        (
            ["J001,480,UNLOAD,false,30,A,", "J001,490,LOAD,false,30,,B"],
            ["J001,495,30"],
            "duplicate job_id 'J001'",
        ),
        (
            ["J001,480,UNLOAD,false,30,A,", "J002,490,LOAD,false,30,,B"],
            ["J001,495,30"],
            "job 'J002': no realization",
        ),
        (
            ["J001,480,UNLOAD,false,30,A,"],
            ["J001,495,30", "J999,500,30"],
            "realization 'J999': no planned job",
        ),
    ],
    ids=["duplicate_job_id", "missing_realization", "unplanned_realization"],
)
def test_inconsistent_plan_and_realization_are_rejected(
    tmp_path, plan_rows, realization_rows, message
):
    _assert_rejected(tmp_path, plan_rows, realization_rows, message)
