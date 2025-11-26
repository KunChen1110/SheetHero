import argparse
import logging
import sys

from core.agent import SheetBrain
from config.settings import Config
from utils.output_formatter import format_output_user_mode, format_output_verbose_mode
from utils.logger import set_log_level


def main():
    parser = argparse.ArgumentParser(description="SheetBrain - AI-powered Excel analysis")

    # === Required Arguments ===
    parser.add_argument("question", help="Question to ask about the Excel file")
    parser.add_argument("excel_paths", nargs='+', help="Path(s) to the Excel file(s)")

    # === Optional Arguments ===
    parser.add_argument("--output-mode", choices=["text", "file"], default="text",
                        help="Choose 'text' for inline answers or 'file' to save results")
    parser.add_argument("--output-file",
                        help="When --output-mode=file, optional custom output filepath")
    parser.add_argument("--verbose", action="store_true", default=False,
                        help="Enable verbose output mode (default: user-friendly concise mode)")
    """ Example: 
    cd src/backend 
    python3 main.py \
    "output a form with each tutor's name, day ,their time slot, location of their tutor meeting and the amount of the students attending the meetings." \
    ../../dataset/Task02/tc02_input01.csv \
    ../../dataset/Task02/tc02_input02.csv \
    ../../dataset/Task02/tc02_input03.csv \
    ../../dataset/Task02/tc02_input04.csv \
    ../../dataset/Task02/tc02_input05.csv \
    --output-mode file \
    --verbose
    """
    args = parser.parse_args()

    try:
        config = Config()
        config.output_mode = args.output_mode
        config.output_file = args.output_file
        config.verbose = args.verbose

        # Configure logger verbosity
        log_level = logging.INFO if config.verbose else logging.ERROR
        set_log_level(log_level)

        # Create agent
        agent = SheetBrain(excel_paths=args.excel_paths, config=config)

        # Run the actual analysis with the user's question
        result = agent.run(user_question=args.question)

        # Display Results based on verbose mode
        if config.verbose:
            output = format_output_verbose_mode(result, args.excel_paths, args.question)
        else:
            output = format_output_user_mode(
                result,
                args.excel_paths,
                args.question,
                output_mode=config.output_mode
            )
        
        print(output)

        # Exit with success code (0) if analysis worked, failure code (1) otherwise
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()