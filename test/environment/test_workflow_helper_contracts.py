import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.environment.spreadsheet.tools.workflows import (
    add_rank_column,
    build_correlation_matrix_table,
    build_group_summary,
    compute_feature_correlations,
    compute_percentage_share,
    compute_ratio_column,
    compute_weighted_score,
    summarize_numeric_column,
)
from backend.environment.spreadsheet.tools.output import ExcelOutputWriter


def test_summarize_numeric_column_exposes_explicit_extrema_row_contract():
    df = pd.DataFrame(
        {
            "Day": ["Mon", "Tue", "Wed", "Thu"],
            "Sales": [100, 250, 50, 250],
        }
    )

    result = summarize_numeric_column(df, value_col="Sales")

    assert result["stats"] == {
        "total": 650,
        "average": 162.5,
        "min": 50,
        "max": 250,
    }
    assert result["min_value"] == 50
    assert result["max_value"] == 250
    assert result["row_number_offset"] == 2
    assert result["highlight_rows"]["max"] == [3, 5]
    assert result["highlight_rows"]["min"] == [4]
    assert result["max_output_row_numbers"] == [3, 5]
    assert result["min_output_row_numbers"] == [4]
    assert result["output_row_numbers"] == result["max_output_row_numbers"]


def test_atomic_transform_helpers_return_dataframe_with_metadata_contract():
    df = pd.DataFrame(
        {
            "Revenue": [100, 50],
            "Cost": [25, 10],
            "Votes": [8, 2],
            "Quality": [4, 10],
            "Region": ["A", "A"],
        }
    )

    ratio_result = compute_ratio_column(df, "Revenue", "Cost", output_col="Revenue/Cost")
    share_result = compute_percentage_share(df, "Revenue", output_col="Share", group_col="Region")
    score_result = compute_weighted_score(df, ["Votes", "Quality"], weights=[0.75, 0.25], output_col="Score")
    rank_result = add_rank_column(score_result["output_df"], sort_col="Score", rank_col="Rank")

    for result in (ratio_result, share_result, score_result, rank_result):
        assert set(result) >= {"output_df", "detail_data", "metadata"}
        assert isinstance(result["output_df"], pd.DataFrame)

    assert ratio_result["metadata"]["formula"] == "Revenue / Cost"
    assert share_result["metadata"]["group_col"] == "Region"
    assert score_result["metadata"]["weights"] == [0.75, 0.25]
    assert rank_result["metadata"]["row_number_offset"] == 2
    assert rank_result["output_row_numbers"] == [2, 3]


def test_group_summary_accepts_llm_friendly_source_to_agg_mapping():
    df = pd.DataFrame(
        {
            "Region": ["North", "North", "South"],
            "Sales": [10, 20, 5],
        }
    )

    result = build_group_summary(
        df,
        group_cols=["Region"],
        aggregations={"Sales": "sum"},
        sort_by=["Total Sales"],
        ascending=False,
    )

    assert result["output_df"].columns.tolist() == ["Region", "Total Sales"]
    assert result["output_df"].iloc[0].to_dict() == {"Region": "North", "Total Sales": 30}
    assert result["metadata"]["aggregations"] == {"Total Sales": ("Sales", "sum")}


def test_correlation_matrix_output_df_keeps_row_label_column_for_direct_write():
    df = pd.DataFrame(
        {
            "A": [1, 2, 3],
            "B": [2, 4, 6],
            "C": [3, 2, 1],
        }
    )

    result = build_correlation_matrix_table(df, numeric_columns=["A", "B", "C"])

    assert result["output_df"].columns.tolist() == ["Variable", "A", "B", "C"]
    assert result["output_df"]["Variable"].tolist() == ["A", "B", "C"]
    assert result["detail_data"][0] == ["Variable", "A", "B", "C"]


def test_feature_correlations_ignores_target_if_in_feature_list():
    df = pd.DataFrame(
        {
            "Survived": [0, 1, 1, 0],
            "Sex": ["male", "female", "female", "male"],
            "Fare": [10, 20, 30, 12],
        }
    )

    result = compute_feature_correlations(
        df,
        target_col="Survived",
        feature_cols=["Survived", "Sex", "Fare"],
        round_digits=3,
    )

    assert result["feature_cols"] == ["Sex", "Fare"]
    assert result["output_df"].columns.tolist() == ["Sex", "Fare"]


def test_output_writer_unwraps_helper_result_output_df_for_compatibility():
    df = pd.DataFrame({"Revenue": [100], "Cost": [25]})
    helper_result = compute_ratio_column(df, "Revenue", "Cost", output_col="Revenue/Cost")
    writer = ExcelOutputWriter(workbook=None, excel_path="/tmp/input.xlsx", output_path=None, temp_files=[])

    rows = writer._coerce_tabular_rows(helper_result)

    assert rows == [["Revenue", "Cost", "Revenue/Cost"], [100, 25, 4.0]]
