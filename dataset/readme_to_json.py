import re
import json

# Here is a converter that can parse the readme to json
# The readme should follow the format
# Test ID -> Title -> Spreadsheet -> Answer -> Output -> Feedback
#

def parse_readme_to_tasks(readme_text):
    tasks = []

    pattern = r"##\s*Test\s*(\d+)(.*?)(?=##\s*Test|\Z)"
    matches = re.findall(pattern, readme_text, re.S)

    for task_id, block in matches:
        task_data = {
            "task_id": f"Test {task_id}",
            "title": None,
            "spreadsheets": [],
            "prompt": None,
            "expected_output_file": [],
            "feedback": None
        }

        # Title
        title_match = re.search(r"###\s*(.*?)\n", block)
        if title_match:
            task_data["title"] = title_match.group(1).strip()

        # Spreadsheets - 
        spreadsheet_matches = re.findall(r"\[(.*?)\]\((.*?)\)", block)
        for label, path in spreadsheet_matches:
           
            # Get the link of input files
            filename = path.split('/')[-1]  
            if not filename.startswith('output'):   # Not start with output
                task_data["spreadsheets"].append(path)

        # Get the link of output files
        for label, path in spreadsheet_matches:
            filename = path.split('/')[-1] 
            if filename.startswith('output') and path.endswith('.xlsx'):
                task_data["expected_output_file"].append(path)
                

        # Prompt
        prompt_match = re.search(r"###\s*Prompt\s*(.*?)(?=###|\Z)", block, re.S)
        if prompt_match:
            prompt = prompt_match.group(1).strip()
            # clean the prompt
            prompt = re.sub(r"###.*", "", prompt, flags=re.S)
            task_data["prompt"] = prompt.strip()

        # Feedback
        fb_match = re.search(r"###\s*Feedback\s*(.*?)(?=###|\Z)", block, re.S)
        if fb_match:
            feedback = fb_match.group(1).strip()
            task_data["feedback"] = feedback

        tasks.append(task_data)

    return tasks


# === Example usage ===
if __name__ == "__main__":
    with open("DatasetV1.md", "r", encoding="utf-8") as f:
        readme_text = f.read()

    tasks_json = parse_readme_to_tasks(readme_text)

    with open("dataset.json", "w", encoding="utf-8") as f:
        json.dump(tasks_json, f, indent=4, ensure_ascii=False)

    print("Json has been created successfully !")
