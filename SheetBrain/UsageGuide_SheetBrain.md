# Installation and Usage Guide

## System Requirements

- Python 3.8 or higher
- pip3 (Python package manager for Python 3)
- OpenAI API key (for LLM functionality)

## Installation Steps

### 1. Clone or Download the Project

```bash
# If using git
git clone <repository-url>
cd team29_project

# Or directly download and extract the project folder
```

### 2. Create Virtual Environment (Recommended)

Using a virtual environment helps avoid dependency conflicts:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Navigate to backend directory
cd src/backend

# Install all dependencies
# Use pip3 to ensure Python 3 packages are installed
pip3 install -r requirements.txt

# If pip3 is not available, try:
# python3 -m pip install -r requirements.txt
```

**Note:** On macOS and Linux, use `pip3` instead of `pip` to ensure packages are installed for Python 3. On Windows, `pip` usually works fine.

### 4. Configure API Key

Set up your OpenAI API key (required):

```bash
# macOS/Linux:
export OPENAI_API_KEY="your-api-key-here"

# Windows (PowerShell):
$env:OPENAI_API_KEY="your-api-key-here"

# Windows (CMD):
set OPENAI_API_KEY=your-api-key-here
```

Alternatively, create a `.env` file (requires `python-dotenv`):

```bash
# Create .env file in project root directory
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

### 5. Verify Installation

```bash
# Run test in src/backend directory
cd src/backend
python3 -c "from core import SheetBrain; print('✓ Installation successful!')"
```

## Usage

### Method 1: Run Example Script (Quick Start)

The easiest way to get started is to run the example script:

```bash
# Navigate to backend directory
cd src/backend

# Run the example script
python3 run_example.py
```

This script will:
- Use `examples/example_table.xlsx` as the example file
- Demonstrate how to use SheetBrain with a sample question
- Show you the complete output format

**What to expect:**
- The script will analyze the example Excel file
- It will ask: "What is the total landings (tonnes live weight) for Scotland in 2023, and how does it compare to the total landings for England, Wales, and N.I.?"
- You'll see the three-stage analysis process (Understanding → Execution → Validation)
- Final results including answer, confidence score, and validation status

This is the recommended way to verify your installation is working correctly!

### Method 2: Command Line Interface (CLI)

Once you're familiar with the example, you can use the CLI to analyze your own Excel files:

```bash
# Navigate to backend directory
cd src/backend

# Basic usage
python3 main.py <excel-file-path> "<your-question>"

# Example
python3 main.py ../dataset/Task1/input1.xlsx "What is the total budget?"

# Advanced options
python3 main.py <excel-file-path> "<question>" \
    --max-turns 5 \
    --token-budget 15000 \
    --verbose
```

**CLI Arguments:**
- `excel_path`: Path to Excel file (required)
- `question`: Question to ask (required)
- `--max-turns`: Maximum execution turns (default: 3)
- `--token-budget`: Token budget (default: 10000)
- `--no-validation`: Disable validation stage
- `--no-understanding`: Disable understanding stage
- `--api-key`: Override API key
- `--base-url`: Custom API base URL
- `--deployment`: Model deployment name
- `--verbose, -v`: Enable verbose logging

### Method 3: Use in Python Code

For programmatic use, you can import and use SheetBrain in your own Python scripts:

```python
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'backend'))

from core import SheetBrain

# Initialize SheetBrain
agent = SheetBrain(excel_path="path/to/your/file.xlsx")

# Run analysis
result = agent.run(
    user_question="Your question",
    max_turns=3,
    enable_validation=True,
    enable_understanding=True
)

# View results
print(f"Success: {result['success']}")
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence_score']:.2f}")
```

## Project Structure

```
team29_project/
├── src/
│   └── backend/              # Backend code
│       ├── core/             # Core functionality
│       │   └── agent.py      # SheetBrain main class
│       ├── modules/          # Processing modules
│       │   ├── understanding.py
│       │   ├── execution.py
│       │   └── validation.py
│       ├── utils/            # Utility classes
│       │   ├── excel_toolkit.py
│       │   └── logger.py
│       ├── config/           # Configuration management
│       │   └── settings.py
│       ├── examples/         # Example files
│       ├── main.py           # CLI entry point
│       ├── run_example.py    # Example script
│       └── requirements.txt  # Dependency list
├── dataset/                  # Dataset
├── docs/                     # Documentation
└── assets/                   # Resource files
```

## Common Issues

### 1. Import Errors

If you encounter `ModuleNotFoundError`:

```bash
# Make sure you're in the correct directory
cd src/backend

# Check Python path
python3 -c "import sys; print(sys.path)"

# Reinstall dependencies using pip3
pip3 install -r requirements.txt --force-reinstall

# Or use python3 -m pip
python3 -m pip install -r requirements.txt --force-reinstall
```

### 2. API Key Errors

If you see "OpenAI API key not found":

```bash
# Check environment variable
echo $OPENAI_API_KEY  # macOS/Linux
echo %OPENAI_API_KEY%  # Windows

# Reset it
export OPENAI_API_KEY="your-key-here"
```

### 3. File Path Issues

Use absolute paths or paths relative to the current working directory:

```bash
# Good practice
python3 main.py /absolute/path/to/file.xlsx "question"
python3 main.py ../dataset/Task1/input1.xlsx "question"

# Avoid
python3 main.py ~/file.xlsx "question"  # May cause issues
```

### 4. Dependency Version Conflicts

If you encounter version conflicts:

```bash
# Use virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
pip3 install -r requirements.txt
```

## Development Environment Setup

### Install Development Dependencies

```bash
pip3 install pytest pytest-cov black flake8 mypy
```

### Code Formatting

```bash
black src/backend/
```

### Run Tests

```bash
pytest tests/
```

## Next Steps

- Check `docs/SheetBrain/README.md` for detailed API documentation
- Check `src/backend/run_example.py` for usage examples
- Check `docs/` directory for project architecture and design

## Getting Help

If you encounter issues:
1. Check documentation in the `docs/` directory
2. Review code comments (detailed Chinese comments in the code)
3. Run example scripts to verify environment is correctly configured
