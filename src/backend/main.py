import argparse
import sys

from core.agent import SheetBrain, build_output_preferences
from config.settings import Config


def main():
    parser = argparse.ArgumentParser(description="SheetBrain - AI-powered Excel analysis")

    # === Required Arguments ===
    parser.add_argument("excel_path", help="Path to the Excel file to analyze")
    parser.add_argument("question", help="Question to ask about the Excel file")

    # === Optional Arguments ===
    parser.add_argument("--max-turns", type=int, default=3,
                        help="Maximum number of execution turns (default: 3)")

    parser.add_argument("--no-validation", action="store_true",
                        help="Disable validation stage")
    parser.add_argument("--no-understanding", action="store_true",
                        help="Disable understanding stage")

    parser.add_argument("--token-budget", type=int, default=10000,
                        help="Token budget for context generation (default: 10000)")

    parser.add_argument("--api-key", help="OpenAI API key (overrides config)")
    parser.add_argument("--base-url", help="OpenAI base URL (overrides config)")
    parser.add_argument("--deployment", help="Model deployment name (overrides config)")

    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")

    parser.add_argument("--output-mode", choices=["text", "file"], default="text",
                        help="Choose 'text' for inline answers or 'file' to save results (default: text)")
    parser.add_argument("--output-file",
                        help="Path to save results when --output-mode=file (optional)")

    args = parser.parse_args()

    try:
        config = Config()

        # Create agent
        agent = SheetBrain(excel_paths=args.excel_path,config=config)

        # Run the actual analysis with the user's question
        result = agent.run(user_question=args.question)

        # Display Results
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)

        # Show key information about the analysis
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
        if args.verbose and result['improvement_feedback']:
            print(f"\nImprovement Feedback:")
            print(result['improvement_feedback'])

        print("="*60)

        # Exit with success code (0) if analysis worked, failure code (1) otherwise
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()