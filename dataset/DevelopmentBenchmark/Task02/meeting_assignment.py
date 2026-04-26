import pandas as pd

# === Step 1. Read 5 excel files===
df_employee = pd.read_csv("tc02_input01.csv")      # academics list
df_role = pd.read_csv("tc02_input02.csv")          # academic roles
df_student = pd.read_csv("tc02_input03.csv")       # student assignments
df_tutor_info = pd.read_csv("tc02_input04.csv")    # tutor availability
df_meeting = pd.read_csv("tc02_input05.csv")       # tutor meetings


# === Step 2. cleaning the files ===
for df in [df_employee, df_role, df_student, df_tutor_info, df_meeting]:
    df.columns = df.columns.str.strip()
    # 清理空格
    if 'Name' in df.columns:
        df['Name'] = df['Name'].astype(str).str.strip()
    if 'Tutor Name' in df.columns:
        df['Tutor Name'] = df['Tutor Name'].astype(str).str.strip()
    if 'Assigned Tutor' in df.columns:
        df['Assigned Tutor'] = df['Assigned Tutor'].astype(str).str.strip()

# === Step 3. Grouping the students by the tutor ===
tutor_students = (
    df_student.groupby("Assigned Tutor")["Name"]
    .apply(lambda x: ", ".join(x))
    .reset_index()
    .rename(columns={"Assigned Tutor": "Tutor Name", "Name": "Students Assigned"})
)

# === Step 4. Merge the meetings with the student group ===
df_output = pd.merge(df_meeting, tutor_students, on="Tutor Name", how="left")

# === Step 5. Sort the output  ===
df_output = df_output.sort_values(by=["Tutor Name", "Day", "Time Slot"])
df_output.to_excel("output2.xlsx", index=False)

print("✅ Output saved to output_tutor_meetings.xlsx")
print(df_output.head())
