from pathlib import Path

import pytest

from dock_scheduling.csv_loader import CsvParseError, load_scenario
from dock_scheduling.domain import (
    DockDefinition,
    JobPlan,
    JobRealization,
    OperationType,
    PlanSnapshot,
    RealizationDefinition,
    ScenarioDefinition,
)
from dock_scheduling.scenario_validation import ScenarioValidationError

EXAMPLES_DIR = Path(__file__).parent.parent / "data" / "examples"
DOCKS = (DockDefinition("D01"), DockDefinition("D02"))
PLAN_HEADER = (
    "job_id,planned_arrival_min,operation,priority,"
    "estimated_service_time_min,unload_section,load_section"
)
REALIZATION_HEADER = "job_id,actual_arrival_min,actual_service_time_min"
VALID_PLAN_ROW = "J001,480,UNLOAD,false,30,A,"
VALID_REALIZATION_ROW = "J001,495,30"


def _load(
    tmp_path: Path,
    plan_rows: list[str],
    realization_rows: list[str],
    plan_header: str = PLAN_HEADER,
) -> ScenarioDefinition:
    plan_path = tmp_path / "plan.csv"
    realization_path = tmp_path / "realization.csv"
    plan_path.write_text("\n".join([plan_header, *plan_rows]) + "\n")
    realization_path.write_text(
        "\n".join([REALIZATION_HEADER, *realization_rows]) + "\n"
    )
    return load_scenario(plan_path, realization_path, DOCKS)


def _parse_errors(
    tmp_path: Path,
    plan_rows: list[str],
    realization_rows: list[str],
    plan_header: str = PLAN_HEADER,
) -> tuple[str, ...]:
    with pytest.raises(CsvParseError) as excinfo:
        _load(tmp_path, plan_rows, realization_rows, plan_header)
    return excinfo.value.errors


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


def test_rows_are_parsed_into_scenario_in_input_order(tmp_path):
    scenario = _load(
        tmp_path,
        plan_rows=[
            "J003,495,BOTH,false,60,A,C",
            "J001,-120,UNLOAD,false,45,A,",
            "J002,480,LOAD,true,30,,B",
        ],
        realization_rows=["J002,470,30", "J003,1450,60", "J001,90,45"],
    )

    assert scenario == ScenarioDefinition(
        plan=PlanSnapshot(
            jobs=(
                JobPlan("J003", 495, OperationType.BOTH, False, 60, "A", "C"),
                JobPlan("J001", -120, OperationType.UNLOAD, False, 45, "A", None),
                JobPlan("J002", 480, OperationType.LOAD, True, 30, None, "B"),
            )
        ),
        realization=RealizationDefinition(
            jobs=(
                JobRealization("J002", 470, 30),
                JobRealization("J003", 1450, 60),
                JobRealization("J001", 90, 45),
            )
        ),
        docks=DOCKS,
    )


@pytest.mark.parametrize("value", ["True", "FALSE", "1", "0", "yes", "", " true"])
def test_priority_outside_true_false_is_rejected(tmp_path, value):
    errors = _parse_errors(
        tmp_path, [f"J001,480,UNLOAD,{value},30,A,"], [VALID_REALIZATION_ROW]
    )

    assert errors == (
        (
            f"{tmp_path / 'plan.csv'} line 2, field 'priority': "
            f"invalid value {value!r}, expected true or false"
        ),
    )


@pytest.mark.parametrize("value", ["12a", "1.5", "", " 30", "+30", "1_000"])
def test_malformed_integer_is_rejected(tmp_path, value):
    errors = _parse_errors(tmp_path, [VALID_PLAN_ROW], [f"J001,{value},30"])

    assert errors == (
        (
            f"{tmp_path / 'realization.csv'} line 2, field 'actual_arrival_min': "
            f"invalid value {value!r}, expected an integer"
        ),
    )


@pytest.mark.parametrize("value", ["load", "Unload", "LOADING", ""])
def test_invalid_operation_is_rejected(tmp_path, value):
    errors = _parse_errors(
        tmp_path, [f"J001,480,{value},false,30,A,"], [VALID_REALIZATION_ROW]
    )

    assert errors == (
        (
            f"{tmp_path / 'plan.csv'} line 2, field 'operation': "
            f"invalid value {value!r}, expected LOAD or UNLOAD or BOTH"
        ),
    )


def test_parse_errors_from_both_files_are_collected(tmp_path):
    errors = _parse_errors(
        tmp_path,
        [VALID_PLAN_ROW, "J002,soon,LOAD,false,30,,B"],
        [VALID_REALIZATION_ROW, "J002,500,long"],
    )

    assert errors == (
        (
            f"{tmp_path / 'plan.csv'} line 3, field 'planned_arrival_min': "
            "invalid value 'soon', expected an integer"
        ),
        (
            f"{tmp_path / 'realization.csv'} line 3, field 'actual_service_time_min': "
            "invalid value 'long', expected an integer"
        ),
    )


def test_header_with_missing_and_unexpected_column_is_rejected(tmp_path):
    header = PLAN_HEADER.replace("priority", "is_priority")

    errors = _parse_errors(
        tmp_path, [VALID_PLAN_ROW], [VALID_REALIZATION_ROW], plan_header=header
    )

    assert len(errors) == 1
    assert "missing ['priority'], unexpected ['is_priority']" in errors[0]


def test_plan_columns_may_appear_in_any_order(tmp_path):
    header = (
        "load_section,unload_section,estimated_service_time_min,priority,"
        "operation,planned_arrival_min,job_id"
    )

    scenario = _load(
        tmp_path, ["B,A,60,true,BOTH,-15,J001"], ["J001,10,60"], plan_header=header
    )

    assert scenario.plan.jobs == (
        JobPlan("J001", -15, OperationType.BOTH, True, 60, "A", "B"),
    )


def test_header_with_duplicated_column_is_rejected(tmp_path):
    header = PLAN_HEADER + ",job_id"

    errors = _parse_errors(
        tmp_path, [VALID_PLAN_ROW + "J001"], [VALID_REALIZATION_ROW], plan_header=header
    )

    assert len(errors) == 1
    assert "duplicated ['job_id']" in errors[0]


@pytest.mark.parametrize(
    "row", ["J001,480,UNLOAD,false,30,A", "J001,480,UNLOAD,false,30,A,,X"]
)
def test_row_with_wrong_cell_count_is_rejected(tmp_path, row):
    errors = _parse_errors(tmp_path, [row], [VALID_REALIZATION_ROW])

    assert errors == (
        (
            f"{tmp_path / 'plan.csv'} line 2: expected 7 cells per row, "
            "row has a different number"
        ),
    )


def test_scenario_validation_runs_after_parsing(tmp_path):
    with pytest.raises(ScenarioValidationError) as excinfo:
        _load(tmp_path, ["J001,480,LOAD,false,30,A,"], [VALID_REALIZATION_ROW])

    assert excinfo.value.errors == (
        "job 'J001': LOAD requires a non-empty load_section",
        "job 'J001': LOAD must not define unload_section",
    )
