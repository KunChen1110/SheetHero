import os
import pandas as pd
import re
from glob import glob
import math

OUTPUT_EXCEL = "tc21_output01.xlsx"

def normalize_header(h):
    """Normalize headers: remove spaces/special chars, lowercase."""
    return re.sub(r'[^a-zA-Z0-9]', '', str(h).strip().lower())


def safe_str(x):
    """Convert any value (including float/NaN) to safe string."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x).strip()


def calculate_capability(row):
    """Calculate capability score based on clean data."""
    years = float(row.get("yearsofexperience", 0) or 0)

    skills_raw = safe_str(row.get("keyskills", ""))
    skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    num_skills = len(skills)

    personality = float(row.get("personalityscore", 0) or 0)

    return years * 0.5 + num_skills * 0.3 + personality  * 0.2


def load_candidate(file_path):
    """Load one-row horizontal Excel file."""
    try:
        df = pd.read_excel(file_path)
    except:
        return None

    if df.empty:
        return None

    # Normalize headers
    df.columns = [normalize_header(c) for c in df.columns]
    
    row = {col: safe_str(df.iloc[0][col]) for col in df.columns}

    # Skip if name missing
    name = row.get("name", "")
    if not name:
        return None

    row["capability"] = calculate_capability(row)
    row["file"] = os.path.basename(file_path)

    return row


def main():
    excel_files = glob("./*.xlsx")
    candidates = []

    for f in excel_files:
        if f.endswith(OUTPUT_EXCEL):  
            continue

        candidate = load_candidate(f)
        if candidate:
            candidates.append(candidate)

    ranked = sorted(candidates, key=lambda x: x["capability"], reverse=True)

    output_rows = []
    for c in ranked:
        output_rows.append({
            "candidate": c.get("name", ""),
            "capability_ranking": c.get("capability", 0),
            "skills": c.get("keyskills", ""),
            "education": c.get("education", ""),
            "past_companies": c.get("pastcompanies", ""),
            "years_of_experience": c.get("yearsofexperience", ""),
            "personality_score": c.get("personalityscore", "")
        })

    pd.DataFrame(output_rows).to_excel(OUTPUT_EXCEL, index=False)

    print(f"\nRanking saved to {OUTPUT_EXCEL}\n")


if __name__ == "__main__":
    main()


