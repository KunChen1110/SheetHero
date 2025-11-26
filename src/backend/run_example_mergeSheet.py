#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
 * Standalone demonstration script for the SheetBrain library.
 *
 * This file shows how to use SheetBrain programmatically within your own
 * Python code, as an alternative to using the command-line interface.
 * It includes practical examples of configuration and error handling.
 *
 * Key Features Demonstrated:
 * - Direct library usage in Python scripts
 * - Multiple configuration approaches (default vs. custom)
 * - File existence checking for better error messages
 * - Try-catch exception handling
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

import sys     # System-specific parameters (path manipulation, exit codes)
import os      # Operating system interface (file checking, path operations)

# Add the script's directory to Python's module search path
# This is CRITICAL: it tells Python where to find our custom modules (core, config)
# When running a script directly, Python may not automatically know about nearby packages
# sys.path[0] ensures our local files take priority over installed packages
sys.path.insert(0, os.path.dirname(__file__))

# Import the SheetBrain class - the main engine for Excel analysis
from core import SheetBrain
# from config.settings import Config  # Uncomment if using custom configuration


def main():
    """
     * Main demonstration function for SheetBrain usage.
     *
 * This function walks through a complete example of analyzing an Excel/CSV file
     * with a natural language question. It demonstrates:
     *
     * 1. **Setup Phase**: Define file path and question, verify file exists
     * 2. **Initialization Phase**: Create SheetBrain agent with configuration
     * 3. **Execution Phase**: Run the analysis with error handling
     * 4. **Output Phase**: Display formatted results
     *
     * Configuration Options Shown:
     * - Option 1: Minimal setup (uses default configuration)
     * - Option 2: Custom configuration (commented out, but shows full control)
     *
     * Error Handling:
     * - Pre-checks for file existence before analysis
     * - Try-catch block to handle API errors, missing keys, or analysis failures
     *
     * @return: None (results printed to console)
     * @throws: None (exceptions caught and handled internally)
    """

    print("🚀 [Example] Initializing SheetBrain...")

    # === Step 1: Define Analysis Parameters ===
    # Specify which Excel file(s) to analyze and what question to ask
    # Use path relative to this script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # For multi-file example, specify multiple spreadsheet files (Excel or CSV)
    # This example uses two separate .xlsx files, but .csv files can be mixed in too
    excel_paths = [
        os.path.join(script_dir, "examples", "academicYearAverage.xlsx"),
        os.path.join(script_dir, "examples", "studentDetail.xlsx"),
    ]
    
    # Multi-file question: Calculate average across multiple files/classes
    user_question = "Who is the student with the highest average mark majoring in CS?"

    # === Step 2: Validate Input ===
    # Check if all Excel files actually exist BEFORE trying to analyze them
    # This gives a clear, early error message instead of a confusing crash later
    # os.path.exists() returns True if the file is found, False otherwise
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

    # === Step 3: Initialize the Agent ===
    # Create a SheetBrain instance to perform the analysis

    # Option 1: Simple initialization with default settings
    # - Uses environment variables for API key and other config
    # - Sets a token budget of 5000 (limits AI context size)
    # - Pass excel_paths as a list for multi-file support
    agent = SheetBrain(excel_paths=excel_paths, total_token_budget=5000)

    # Option 2: Advanced initialization with custom configuration (commented out)
    # - Uncomment this section for full control over agent behavior
    # - Config object lets you set max turns, enable/disable stages, etc.
    # - Useful when you want reproducible settings across multiple analyses
    # config = Config(
    #     max_turns=5,
    #     enable_validation=True,
    #     enable_understanding=True
    # )
    # agent = SheetBrain(excel_path=excel_path, config=config)

    print("📋 [Example] Starting analysis...")

    # === Step 4: Execute Analysis with Error Handling ===
    # Wrap the analysis in a try-except block to catch and handle any problems
    # This could include: API key errors, network issues, invalid Excel file, etc.
    try:
        # Call the agent's run() method to start the analysis
        # Parameters:
        # - user_question: What you want to know about the data
        # - max_turns: How many times AI can refine its answer (default: 3)
        # - enable_validation: Whether to double-check the answer (True/False)
        # - enable_understanding: Whether to pre-analyze the Excel structure
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