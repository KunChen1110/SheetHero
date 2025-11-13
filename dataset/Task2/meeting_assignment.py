import pandas as pd

# === Step 1. 读取五张表（假设都是 xlsx 或 csv）===
# 你可以按实际路径替换
df_employee = pd.read_csv("academics_list.csv")      # Employee ID, Name, Department, Email
df_role = pd.read_csv("academic_roles.csv")              # Employee ID, Name, Role, Department
df_student = pd.read_csv("student_assignments.csv")        # Student ID, Name, Program, Year, Assigned Tutor
df_tutor_info = pd.read_csv("tutor_availability.csv")  # Name, Email, Available Days, Preferred Times, Max Students
df_meeting = pd.read_csv("tutor_meetings.csv")  # Tutor Name, Day, Time Slot, Room, Students Assigned

# === Step 2. 清洗列名（有的表中名字字段有多余空格，比如 "Smith  John"）===
for df in [df_employee, df_role, df_student, df_tutor_info, df_meeting]:
    df.columns = df.columns.str.strip()
    # 清理空格
    if 'Name' in df.columns:
        df['Name'] = df['Name'].astype(str).str.strip()
    if 'Tutor Name' in df.columns:
        df['Tutor Name'] = df['Tutor Name'].astype(str).str.strip()
    if 'Assigned Tutor' in df.columns:
        df['Assigned Tutor'] = df['Assigned Tutor'].astype(str).str.strip()

# === Step 3. 把学生按导师分组（一个导师对应多个学生）===
tutor_students = (
    df_student.groupby("Assigned Tutor")["Name"]
    .apply(lambda x: ", ".join(x))
    .reset_index()
    .rename(columns={"Assigned Tutor": "Tutor Name", "Name": "Students Assigned"})
)

# === Step 4. 合并导师日程（Meeting）和学生分配信息 ===
df_output = pd.merge(df_meeting, tutor_students, on="Tutor Name", how="left")

# === Step 5. 按导师+时间排序，保存输出 ===
df_output = df_output.sort_values(by=["Tutor Name", "Day", "Time Slot"])
df_output.to_excel("output2.xlsx", index=False)

print("✅ Output saved to output_tutor_meetings.xlsx")
print(df_output.head())
