import argparse
import sys

from core.agent import SheetBrain, build_output_preferences
from config.settings import Config


def main():
    parser = argparse.ArgumentParser(description="SheetBrain - AI-powered Excel analysis")

    # === Required Arguments ===
    parser.add_argument("question", help="Question to ask about the Excel file")
    parser.add_argument("excel_paths", nargs='+', help="Path(s) to the Excel file(s)")


    args = parser.parse_args()

    try:
        config = Config()

        # Create agent
        agent = SheetBrain(excel_paths=args.excel_paths, config=config)

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
        if config.verbose and result['improvement_feedback']:
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