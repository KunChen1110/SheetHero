import re
import json

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
            "expected_output_file": None,
            "feedback": None
        }

        # Title
        title_match = re.search(r"###\s*(.*?)\n", block)
        if title_match:
            task_data["title"] = title_match.group(1).strip()

        # Spreadsheets - 所有不以output开头的文件
        spreadsheet_matches = re.findall(r"\[(.*?)\]\((.*?)\)", block)
        for label, path in spreadsheet_matches:
            # 精确判断：不以output开头（考虑路径分隔符）
            # 检查是否是基础文件名以output开头，而不是路径中包含output
            filename = path.split('/')[-1]  # 获取文件名（最后一部分）
            if not filename.startswith('output'):
                task_data["spreadsheets"].append(path)

        # Expected Output - 以output开头且以.xlsx结尾的文件
        for label, path in spreadsheet_matches:
            filename = path.split('/')[-1]  # 获取文件名（最后一部分）
            if filename.startswith('output') and path.endswith('.xlsx'):
                task_data["expected_output_file"] = path
                break  # 假设每个task只有一个输出文件

        # Prompt
        prompt_match = re.search(r"###\s*Prompt\s*(.*?)(?=###|\Z)", block, re.S)
        if prompt_match:
            prompt = prompt_match.group(1).strip()
            # 清理可能的多余内容
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

    print("dataset.json 已成功生成！")
