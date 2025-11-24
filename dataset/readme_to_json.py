import re
import json

def parse_readme_to_tasks(readme_text):
    """
    Parse a Markdown dataset description into a structured JSON format.

    Each task block follows the structure:
    ## Test X
    ### Title
    ### Spreadsheet
    [spreadsheetN](path...)
    ### Prompt
    ...
    ### Answer
    ...
    ### Output File
    ...
    ### Feedback
    ...

    This parser extracts:
    - task_id
    - title
    - spreadsheets (input files)
    - prompt
    - answer (empty string if missing)
    - expected_output_file
    - feedback
    """

    tasks = []

    # Match each "## Test N" section
    pattern = r"##\s*Test\s*(\d+)(.*?)(?=##\s*Test|\Z)"
    matches = re.findall(pattern, readme_text, re.S)

    for task_id, block in matches:
        # Initialize task object
        task_data = {
            "task_id": f"Test {task_id}",
            "title": None,
            "spreadsheets": [],
            "prompt": None,
            "answer": "",
            "expected_output_file": [],
            "feedback": ""
        }

        # --- Extract Title ---
        title_match = re.search(r"###\s*(.*?)\n", block)
        if title_match:
            task_data["title"] = title_match.group(1).strip()

        # --- Extract file links (spreadsheets & output files) ---
        links = re.findall(r"\[(.*?)\]\((.*?)\)", block)
        for label, path in links:
            filename = path.split('/')[-1]

            # Identify output files: label "outputfileX" + matched filename
            if label.lower().startswith("outputfile"):
                if re.match(r"tc\d+_output\d{2}\.xlsx$", filename):
                    task_data["expected_output_file"].append(path)
                continue

            # Identify input spreadsheets
            if label.lower().startswith("spreadsheet"):
                if re.match(r"tc\d+_input\d{2}\.(csv|xlsx)$", filename):
                    task_data["spreadsheets"].append(path)
                continue

        # --- Extract Prompt section ---
        prompt_match = re.search(r"###\s*Prompt\s*(.*?)(?=###|\Z)", block, re.S)
        if prompt_match:
            task_data["prompt"] = prompt_match.group(1).strip()

        # --- Extract Answer section ---
        answer_match = re.search(r"###\s*Answer\s*(.*?)(?=###|\Z)", block, re.S)
        if answer_match:
            answer = answer_match.group(1).strip()

            # Remove nested Output File segment if present
            answer = re.sub(r"####?\s*Output.*", "", answer, flags=re.S).strip()

            # Normalize empty or null-like answers
            if answer.lower() in ["", "none", "null"]:
                task_data["answer"] = ""
            else:
                task_data["answer"] = answer

        # --- Extract Feedback section ---
        fb_match = re.search(r"###\s*Feedback\s*(.*?)(?=###|\Z)", block, re.S)
        if fb_match:
            task_data["feedback"] = fb_match.group(1).strip()

        tasks.append(task_data)

    return tasks


# === Example usage ===
if __name__ == "__main__":
    # Load the Markdown specification
    with open("DatasetV1.md", "r", encoding="utf-8") as f:
        readme_text = f.read()

    # Convert into structured dataset
    tasks_json = parse_readme_to_tasks(readme_text)

    # Write to dataset.json
    with open("dataset.json", "w", encoding="utf-8") as f:
        json.dump(tasks_json, f, indent=4, ensure_ascii=False)

    print("JSON has been created successfully!")

