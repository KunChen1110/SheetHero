"""
 * File: __init__.py (Modules Package)
 * ------------------------------------
 * Package initialization file for the SheetBrain processing pipeline modules.
 *
 * This file defines the three-stage analysis architecture that powers SheetBrain.
 * Each module represents a distinct stage in the AI's reasoning process when
 * analyzing Excel files. The agent orchestrates these modules in sequence.
 *
 * Three-Stage Pipeline Architecture:
 * ==================================
 *
 * The modules imported here implement a sophisticated AI workflow:
 *
 * 1. **UnderstandingModule** (Stage 1: Comprehension)
 *    - Analyzes the Excel file's structure and content
 *    - Identifies relevant data for the user's question
 *    - Creates a "mental model" of the spreadsheet
 *    - Outputs a structured analysis plan
 *
 * 2. **ExecutionModule** (Stage 2: Action)
 *    - Writes Python code to analyze the data
 *    - Executes code in a sandboxed environment
 *    - Generates an answer based on code execution results
 *    - Returns both the answer and the reasoning process
 *
 * 3. **ValidationModule** (Stage 3: Reflection)
 *    - Critically reviews the execution module's answer
 *    - Checks for errors, oversights, or inconsistencies
 *    - Provides confidence score and improvement feedback
 *    - Either approves the answer or suggests corrections
 *
 * How They Work Together:
 * =======================
 *
 * The SheetBrain agent coordinates these modules in a loop:
 *
 *     User Question
 *          ↓
 *    [UnderstandingModule]  ← "What data is relevant?"
 *          ↓
 *    [ExecutionModule]      ← "Let me write code to analyze it"
 *          ↓
 *    [ValidationModule]     ← "Is this answer correct?"
 *          ↓
 *     ✓ Validation Passed? → Return final answer
 *     ✗ Validation Failed? → Feedback to ExecutionModule → Try again
 *
 * This creates an iterative improvement cycle where the AI learns from
 * its own mistakes, similar to a human analyst double-checking their work.
 *
 * Module Independence:
 * ====================
 * Each module is self-contained and can be:
 * - Tested independently with mock data
 * - Enabled/disabled via configuration
 * - Replaced with alternative implementations
 * - Used separately in other applications
 *
 * The modules communicate via dictionaries (results) and strings (context),
 * making them loosely coupled and maintainable.
"""

# Import the three pipeline stage modules
# These relative imports (with dot) work because this is a package file

# Stage 1: Comprehension - analyzes Excel structure and user question
from .understanding import UnderstandingModule

# Stage 2: Execution - writes and runs analysis code
from .execution import ExecutionModule

# Stage 3: Reflection - validates answers and provides feedback
from .validation import ValidationModule

# __all__ defines the public API of this package
# This controls what gets imported when someone uses: from modules import *
#
# By listing only these three modules, we:
# - Hide internal helper functions and utilities
# - Clearly communicate the package's purpose
# - Prevent accidental usage of private implementation details
# - Enable IDE autocomplete to work correctly
#
# Users typically won't import these directly - the SheetBrain agent
# does that internally. But if they want to use a single module
# for their own purposes, they can import it explicitly.
__all__ = ["UnderstandingModule", "ExecutionModule", "ValidationModule"]

# === Development Note ===
# When adding new analysis stages to SheetBrain:
# 1. Create a new module in this directory (e.g., reporting.py)
# 2. Import it here: from .reporting import ReportingModule
# 3. Add it to __all__: ["UnderstandingModule", "ExecutionModule", "ValidationModule", "ReportingModule"]
# 4. Update the SheetBrain agent in core/agent.py to use the new module
#
# This keeps the architecture modular and extensible.