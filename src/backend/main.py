import argparse
import logging
import sys

# Suppress all logging output to console BEFORE importing other modules
logging.getLogger().setLevel(logging.CRITICAL)
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler):
        root_logger.removeHandler(handler)

from core.agent import SheetHero
from config.settings import Config
from utils.output_formatter import format_output_user_mode

# Suppress all logging output AFTER importing modules (to catch any loggers created during import)
logging.getLogger().setLevel(logging.CRITICAL)
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler):
        root_logger.removeHandler(handler)

# Suppress all child loggers
for logger_name in list(logging.Logger.manager.loggerDict.keys()):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            logger.removeHandler(handler)


def main():
    parser = argparse.ArgumentParser(description="SheetHero - AI-powered Excel analysis")

    # === Required Arguments ===
    parser.add_argument("question", help="Question to ask about the Excel file")
    parser.add_argument("excel_paths", nargs='+', help="Path(s) to the Excel file(s)")

    # === Optional Arguments ===
    parser.add_argument("--output-mode", choices=["text", "file"], default="text",
                        help="Choose 'text' for inline answers or 'file' to save results")
    parser.add_argument("--output-file",
                        help="When --output-mode=file, optional custom output filepath")

    args = parser.parse_args()

    try:
        config = Config()
        config.output_mode = args.output_mode
        config.output_file = args.output_file

        # Create agent
        agent = SheetHero(excel_paths=args.excel_paths, config=config)

        # Run the actual analysis with the user's question
        result = agent.run(user_question=args.question)

        # Display Results (always user mode, verbose logs are in file)
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
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
