# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
 * Main entry point for the SheetBrain Command Line Interface (CLI).
 *
 * This application allows users to analyze Excel files using AI by asking
 * natural language questions like "What are the total sales for each region?"
 * It handles user input, coordinates the analysis process, and displays
 * human-readable results.
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

# Import statements: bringing in required modules from Python's standard library
# and our own project files
import argparse  # Handles command-line argument parsing automatically
import sys       # Provides system-specific functionality like exiting the program
from typing import Optional  # Type hint for optional values (not used directly here)

# Import our custom classes from other modules in the project
from core.agent import SheetBrain, build_output_preferences    # Main AI agent + output helper
from config.settings import Config    # Configuration management for API keys/settings


def main():
    """
     * Main function that runs the SheetBrain CLI application.
     *
     * This is the core function that coordinates the entire workflow:
     * 1. Reads and validates command-line arguments from the user
     * 2. Loads and sets up the application configuration
     * 3. Creates and initializes the AI analysis agent
     * 4. Executes the analysis on the specified Excel file
     * 5. Prints the results in a clean, formatted way
     * 6. Handles any errors that occur during this process
     *
     * @return: None (results are printed to console)
     * @throws: Any exception is caught and handled internally
    """
    # Create an ArgumentParser object to handle command-line inputs
    # Think of this as a smart assistant that validates and organizes user inputs
    parser = argparse.ArgumentParser(description="SheetBrain - AI-powered Excel analysis")

    # === Required Arguments ===
    # These must be provided by the user, in this exact order
    parser.add_argument("excel_path", help="Path to the Excel file to analyze")
    parser.add_argument("question", help="Question to ask about the Excel file")

    # === Optional Arguments ===
    # These have default values and are specified with --flags

    # Control analysis depth: how many times the AI can refine its answer
    parser.add_argument("--max-turns", type=int, default=3,
                        help="Maximum number of execution turns (default: 3)")

    # Disable certain stages of the analysis pipeline
    # action="store_true" means: if flag is present, set value to True
    parser.add_argument("--no-validation", action="store_true",
                        help="Disable validation stage")
    parser.add_argument("--no-understanding", action="store_true",
                        help="Disable understanding stage")

    # Control AI model usage: limit how much data we can send to the AI
    parser.add_argument("--token-budget", type=int, default=10000,
                        help="Token budget for context generation (default: 10000)")

    # Override configuration settings from command line (higher priority than config files)
    parser.add_argument("--api-key", help="OpenAI API key (overrides config)")
    parser.add_argument("--base-url", help="OpenAI base URL (overrides config)")
    parser.add_argument("--deployment", help="Model deployment name (overrides config)")

    # Enable detailed logging for debugging
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")

    # Control how final answers should be delivered
    parser.add_argument("--output-mode", choices=["text", "file"], default="text",
                        help="Choose 'text' for inline answers or 'file' to save results (default: text)")
    parser.add_argument("--output-file",
                        help="Path to save results when --output-mode=file (optional)")

    # Parse all arguments - this will show an error if required args are missing
    args = parser.parse_args()

    # Use try-except to gracefully handle any errors that might occur
    # This prevents the program from crashing and shows user-friendly error messages
    try:
        # Load configuration from environment variables and config files
        # Config.from_env() looks for settings like API keys in your system environment
        config = Config.from_env()

        # Override config values with command-line arguments if they were provided
        # Command-line args take precedence for flexibility (no need to edit config files)
        if args.api_key:
            config.api_key = args.api_key
        if args.base_url:
            config.base_url = args.base_url
        if args.deployment:
            config.deployment = args.deployment

        output_prefs = build_output_preferences(args.output_mode, args.output_file)

        # Create the SheetBrain agent - this is the "brain" that analyzes Excel
        # We pass it the file path(s), config settings, and token budget
        # excel_paths can be a single string or a list of strings
        agent = SheetBrain(
            excel_paths=args.excel_path,
            config=config,
            total_token_budget=args.token_budget,
            output_preferences=output_prefs
        )

        # Run the actual analysis with the user's question
        # The agent will read the Excel file, think about the question, and generate an answer
        # enable_validation=not args.no_validation flips the flag:
        # --no-validation=True means enable_validation=False
        result = agent.run(
            user_question=args.question,
            max_turns=args.max_turns,
            enable_validation=not args.no_validation,
            enable_understanding=not args.no_understanding
        )

        # === Display Results ===
        # Create a formatted output section with visual separators for clarity
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)

        # Show key information about the analysis
        # f-strings allow us to embed variables directly in strings
        # {:.2f} formats numbers to 2 decimal places
        print(f"Success: {'✅' if result['success'] else '❌'}")
        print(f"Answer: {result['answer']}")
        print(f"Confidence: {result['confidence_score']:.2f}/1.0")
        print(f"Iterations: {result['total_iterations']}")
        print(f"Duration: {result['total_duration']:.2f}s")

        # Display any problems found in the Excel file (e.g., missing data, inconsistencies)
        if result['issues_found']:
            print(f"\nIssues Found:")
            for issue in result['issues_found']:
                print(f"  - {issue}")

        # Show detailed feedback only if verbose mode is enabled
        # This gives the AI's suggestions for improving the analysis
        if args.verbose and result['improvement_feedback']:
            print(f"\nImprovement Feedback:")
            print(result['improvement_feedback'])

        print("="*60)

        # Exit with success code (0) if analysis worked, failure code (1) otherwise
        # This is important for shell scripts and automation tools
        # Example: In a bash script, you can check `if [ $? -eq 0 ]; then ...`
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        # If ANY error occurs, print a user-friendly message and exit with error code
        # This prevents the program from crashing and showing scary tracebacks to users
        # file=sys.stderr prints to the error stream instead of standard output
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)  # Exit with error code 1 to indicate failure


# This is a Python best practice pattern called the "main guard"
# It ensures main() only runs when the file is executed directly (python main.py)
# Not when imported as a module in another file (import main)
# __name__ is a special variable set to "__main__" when running directly
if __name__ == "__main__":
    main()