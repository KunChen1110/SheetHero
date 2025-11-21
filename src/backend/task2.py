import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core import SheetBrain, outputMode


def main():

    print("🚀 [Task2] Initializing SheetBrain...")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    excel_paths = [
        os.path.join(script_dir, "..", "..", "dataset", "Task2", "academic_roles.csv"),
        os.path.join(script_dir, "..", "..", "dataset", "Task2", "academics_list.csv"),
        os.path.join(script_dir, "..", "..", "dataset", "Task2", "student_assignments.csv"),
        os.path.join(script_dir, "..", "..", "dataset", "Task2", "tutor_availability.csv"),
        os.path.join(script_dir, "..", "..", "dataset", "Task2", "tutor_meetings.csv"),
    ]

    user_question = "output a form with each tutor's name, day ,their time slot, location of their tutor meeting and the amount of the students attending the meetings."

    missing_files = [path for path in excel_paths if not os.path.exists(path)]
    if missing_files:
        print(f"❌ Excel file(s) not found:")
        for path in missing_files:
            print(f"  - {path}")
        print("Please make sure the example Excel files are in the correct location.")
        return  # Exit the main() function early (but not the whole program)
    
    print(f"✅ Found {len(excel_paths)} Excel file(s) to analyze:")
    for path in excel_paths:
        print(f"  📄 {os.path.basename(path)}")


    # set output mode: by terminal or saved the file
    # example：output_preferences = outputMode("file", "/Users/kun/Desktop/tutor_schedule.xlsx")
    output_prefs = outputMode("file")

    agent = SheetBrain(excel_paths=excel_paths, total_token_budget=5000,
                       output_preferences=output_prefs)


    print("📋 [Task2] Starting analysis...")


    try:

        result = agent.run(
            user_question=user_question,
            max_turns=3,
            enable_validation=True,
            enable_understanding=True
        )

        # === Step 5: Display Results ===
        # Print a formatted report showing the analysis outcome
        # Using f-strings to embed variables in the output text
        print("\n" + "="*60)
        print("FINAL RESULT")
        print("="*60)
        print(f"Success: {result['success']}")  # Boolean: did it work?
        print(f"Total Iterations: {result['total_iterations']}")  # How many attempts?
        print(f"Final Answer: {result['answer']}")  # The AI's actual answer
        print(f"Confidence Score: {result['confidence_score']:.2f}")  # 0.00 to 1.00
        print(f"Validation Passed: {result['validation_passed']}")  # Did self-check pass?
        print(f"Total Duration: {result['total_duration']:.2f}s")  # Time taken in seconds

        # Display any warnings or data quality issues found during analysis
        # This helps users understand limitations of the results
        if result['issues_found']:
            print(f"\nIssues Found:")
            for issue in result['issues_found']:
                print(f"  - {issue}")

        print("="*60)

    except Exception as e:
        # If ANY error occurs during analysis, print a helpful message
        # This catches API errors, file reading errors, analysis failures, etc.
        print(f"❌ Error running analysis: {str(e)}")
        print("Make sure you have the required dependencies installed and your API key is configured.")


# === Main Guard Pattern ===
# This if statement checks if the script is being run directly (python run_example.py)
# vs. being imported as a module (import run_example)
#
# When you run directly: Python sets __name__ to "__main__"
# When you import: Python sets __name__ to the module name ("run_example")
#
# This prevents main() from running automatically when you import the file,
# which is important when building larger applications.
if __name__ == "__main__":
    main()