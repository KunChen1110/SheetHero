import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, deque
from openpyxl import Workbook

# ---------------------------------------------------------
# Step 1: Load input files
# ---------------------------------------------------------
# tasks.xlsx columns: Task ID, Task Name, Duration (hours), Priority
tasks = pd.read_excel("tasks.xlsx")

# dependency.xlsx columns: Task ID, Depends on (empty means no dependency)
deps_df = pd.read_excel("dependency.xlsx")

# ---------------------------------------------------------
# Step 2: Clean data
# ---------------------------------------------------------

# 1. Clean column names
tasks.columns = tasks.columns.str.replace("_x000d_", "", regex=False).str.strip()
deps_df.columns = deps_df.columns.str.replace("_x000d_", "", regex=False).str.strip()

# 2. Clean Task IDs and Depends on cell values
tasks["Task ID"] = tasks["Task ID"].astype(str).str.replace("_x000d_", "", regex=False).str.strip()
deps_df["Task ID"] = deps_df["Task ID"].astype(str).str.replace("_x000d_", "", regex=False).str.strip()
deps_df["Depends on"] = deps_df["Depends on"].astype(str).str.replace("_x000d_", "", regex=False).str.strip()

# 3. Convert 'nan' string or empty strings to real NaN for proper handling
deps_df["Depends on"].replace({'nan': None, '': None}, inplace=True)
deps_df["Depends on"] = deps_df["Depends on"].where(pd.notna(deps_df["Depends on"]), None)

# Debug print to verify
print("Cleaned tasks:")
print(tasks)
print("\nCleaned dependencies:")
print(deps_df)

# ---------------------------------------------------------
# Step 3: Build dependencies dictionary
# ---------------------------------------------------------

# Only keep dependencies whose Task ID exists in tasks
valid_task_ids = set(tasks["Task ID"].tolist())
deps_df = deps_df[deps_df["Task ID"].isin(valid_task_ids)].copy()

# Then rebuild dependency dictionary
dependencies = defaultdict(list)
for _, row in deps_df.iterrows():
    task = row["Task ID"]
    dep = row["Depends on"]
    if dep is None or dep.lower() == 'nan':
        dependencies[task] = []
    else:
        # Only include dependencies that are valid tasks
        if dep in valid_task_ids:
            dependencies[task] = [dep]
        else:
            dependencies[task] = []




# ---------------------------------------------------------
# Step 4: Topological sort using Kahn's algorithm
# ---------------------------------------------------------
incoming = defaultdict(int)  # number of prerequisites
graph = defaultdict(list)    # adjacency list of tasks

# Build graph and count incoming edges
for task, deps in dependencies.items():
    incoming[task] = len(deps)
    for d in deps:
        graph[d].append(task)

# Initialize queue with tasks that have no prerequisites
queue = deque([t for t in dependencies if incoming[t] == 0])
order = []

while queue:
    current = queue.popleft()
    order.append(current)
    for nxt in graph[current]:
        incoming[nxt] -= 1
        if incoming[nxt] == 0:
            queue.append(nxt)

# ---------------------------------------------------------
# Step 5: Schedule tasks based on dependencies
# ---------------------------------------------------------
schedule = []
start_of_day = datetime(2025, 1, 1, 8, 0)
end_times = {}  # store end time of each task

for task_id in order:
    deps = dependencies[task_id]

    # Earliest start time is max end time of dependencies
    if deps:
        earliest_start = max(end_times[d] for d in deps)
    else:
        earliest_start = start_of_day

    # Fetch task duration from tasks table
    duration = float(tasks.loc[tasks["Task ID"] == task_id, "Duration (hours)"].iloc[0])
    end_time = earliest_start + timedelta(hours=duration)

    # Store end time
    end_times[task_id] = end_time

    # Add task info to schedule
    schedule.append({
        "Task ID": task_id,
        "Task Name": tasks.loc[tasks["Task ID"] == task_id, "Task Name"].iloc[0],
        "Priority": tasks.loc[tasks["Task ID"] == task_id, "Priority"].iloc[0],
        "Start Time": earliest_start.strftime("%H:%M"),
        "End Time": end_time.strftime("%H:%M")
    })

schedule_df = pd.DataFrame(schedule)

# ---------------------------------------------------------
# Step 6: Calculate total duration to finish all tasks
# ---------------------------------------------------------
total_hours = (max(end_times.values()) - start_of_day).total_seconds() / 3600
print(f"Total duration to finish all tasks: {total_hours} hours")

# ---------------------------------------------------------
# Step 7: Export schedule to Excel
# ---------------------------------------------------------
wb = Workbook()
ws = wb.active
ws.title = "Task Schedule"

# Write header
ws.append(["Task ID", "Task Name", "Priority", "Start Time", "End Time"])

# Write each task row
for _, row in schedule_df.iterrows():
    ws.append(list(row.values))

# Save Excel file
wb.save("output4.xlsx")
print("Excel file generated: Final_Task_Schedule.xlsx")

