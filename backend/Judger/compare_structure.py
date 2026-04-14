#!/usr/bin/env python3
"""
Compare original vs normalized to see exactly what changed
"""

import pandas as pd
import sys

def compare_files(original_path: str, normalized_path: str):
    """Show detailed comparison of what changed."""

    df_orig = pd.read_excel(original_path)
    df_norm = pd.read_excel(normalized_path)

    print("="*60)
    print("STRUCTURE COMPARISON")
    print("="*60)

    print(f"\nOriginal columns ({len(df_orig.columns)}):")
    for i, col in enumerate(df_orig.columns):
        print(f"  {i+1}. '{col}'")

    print(f"\nNormalized columns ({len(df_norm.columns)}):")
    for i, col in enumerate(df_norm.columns):
        print(f"  {i+1}. '{col}'")

    print(f"\nShapes:")
    print(f"  Original:   {df_orig.shape}")
    print(f"  Normalized: {df_norm.shape}")

    # Check if values changed
    print(f"\nData comparison (first 5 rows):")

    # Find common columns
    common_cols = list(set(df_orig.columns) & set(df_norm.columns))

    if common_cols:
        print(f"\nCommon columns: {common_cols}")

        for col in common_cols[:3]:  # Show first 3 common columns
            print(f"\n  Column '{col}':")
            for i in range(min(5, len(df_orig))):
                orig_val = df_orig.iloc[i][col]
                norm_val = df_norm.iloc[i][col] if i < len(df_norm) else "N/A"

                match = "✅" if str(orig_val) == str(norm_val) else "❌"
                print(f"    Row {i+1}: {match} '{orig_val}' → '{norm_val}'")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    # Column changes
    orig_cols = set(df_orig.columns)
    norm_cols = set(df_norm.columns)

    added_cols = norm_cols - orig_cols
    removed_cols = orig_cols - norm_cols

    if added_cols:
        print(f"\nColumns added (renamed): {added_cols}")
    if removed_cols:
        print(f"Columns removed: {removed_cols}")

    # Check for value changes in common cells
    value_changes = 0
    for col in common_cols:
        for i in range(min(len(df_orig), len(df_norm))):
            if str(df_orig.iloc[i][col]) != str(df_norm.iloc[i][col]):
                value_changes += 1

    if value_changes == 0:
        print("\n✅ No data values were changed - only structure!")
    else:
        print(f"\n⚠️  {value_changes} cells have different values")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        compare_files(sys.argv[1], sys.argv[2])
    else:
        # Default paths
        compare_files(
            "../../artifacts/tests/Task01_output/test1_output.xlsx",
            "../../artifacts/tests/Task01_output/normalized_test1_output.xlsx"
        )