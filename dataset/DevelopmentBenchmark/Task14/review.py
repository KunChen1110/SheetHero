from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]


def analyze_task14_reviews() -> None:
    """
    Original Task14 helper:
    group ratings by (country, brand) and save summary.
    """
    input_path = THIS_FILE.with_name("tc14_input01.csv")
    output_path = THIS_FILE.with_name("output14.xlsx")

    df = pd.read_csv(input_path)

    country_brand_rating = df.groupby(["country", "brand"]).agg(
        avg_rating=("rating", "mean"),
        num_reviews=("rating", "count"),
    ).reset_index()

    country_brand_rating.to_excel(output_path, index=False)
    print(f"✅ Country-brand average rating saved to {output_path}")


def build_comparison_heatmaps() -> None:
    """
    Build two heatmaps from test/output_comparison.xlsx:
      1) correct calculation vs (scenario, category)
      2) expected output format vs (scenario, category)
    """
    comparison_path = PROJECT_ROOT / "test" / "output_comparison.xlsx"

    df = pd.read_excel(comparison_path)

    # Normalize column names (there are trailing spaces in the sheet).
    df = df.rename(columns=lambda c: c.strip() if isinstance(c, str) else c)

    correct_col = "correct calaulation ?"
    format_col = "expected output format ?"
    scenario_col = "scenario"
    category_col = "category"

    # Map textual labels to numeric scores.
    df["correct_calc_score"] = df[correct_col].map(
        {
            "yes": 1.0,
            "no": 0.0,
        }
    )

    df["expected_output_score"] = df[format_col].map(
        {
            "yes": 1.0,
            "slightly different": 0.5,
            "no": 0.0,
        }
    )

    # Pivot tables: average score per (scenario, category).
    pivot_calc = df.pivot_table(
        index=scenario_col,
        columns=category_col,
        values="correct_calc_score",
        aggfunc="mean",
    )

    pivot_output = df.pivot_table(
        index=scenario_col,
        columns=category_col,
        values="expected_output_score",
        aggfunc="mean",
    )

    def plot_heatmap(matrix: pd.DataFrame, title: str, cbar_label: str, out_path: Path) -> None:
        """
        Render a heatmap with clearer contrast and visible missing cells.
        Missing combos are shown in gray instead of white gaps.
        """
        # Annotation: show numbers only where data exists.
        annot_data = matrix.apply(lambda col: col.map(lambda x: "" if pd.isna(x) else f"{x:.2f}"))
        mask = matrix.isna()

        # Palette: gray for missing, then a red→yellow→green gradient (0=wrong, 1=correct).
        gradient = LinearSegmentedColormap.from_list(
            "ryg",
            [
                "#8b0000",  # deep red (wrong)
                "#fee08b",  # yellow (partial)
                "#1a9850",  # green (correct)
            ],
        )
        cmap = gradient.copy()
        cmap.set_bad("#c7c7c7")  # missing -> gray

        plt.figure(figsize=(12, 7))
        sns.heatmap(
            matrix,
            mask=mask,
            annot=annot_data,
            fmt="",
            cmap=cmap,
            vmin=0,
            vmax=1,
            linewidths=0.6,
            linecolor="#f6f6f6",
            cbar_kws={"label": cbar_label, "ticks": [0, 0.25, 0.5, 0.75, 1]},
        )
        plt.title(title)
        plt.ylabel("Scenario")
        plt.xlabel("Category")
        # Slight tilt to avoid label overlap.
        plt.xticks(rotation=20, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(out_path, dpi=200)
        plt.close()

    calc_path = PROJECT_ROOT / "test" / "heatmap_correct_calculation.png"
    output_path = PROJECT_ROOT / "test" / "heatmap_expected_output.png"

    plot_heatmap(
        pivot_calc,
        title="Correct Calculation vs Scenario & Category",
        cbar_label="Correct Calculation (1=yes, 0=no)",
        out_path=calc_path,
    )

    plot_heatmap(
        pivot_output,
        title="Expected Output Format vs Scenario & Category",
        cbar_label="Expected Output Format (1=yes, 0=no, 0.5=slight diff)",
        out_path=output_path,
    )

    print(f"✅ Correct-calculation heatmap saved to {calc_path}")
    print(f"✅ Expected-output-format heatmap saved to {output_path}")


if __name__ == "__main__":
    analyze_task14_reviews()
    build_comparison_heatmaps()
