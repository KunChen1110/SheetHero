"""
SheetHero Processing Pipeline Modules Package
=============================================

Implements a three-stage AI analysis architecture for Excel files:

1. UnderstandingModule (Stage 1) - Analyzes Excel structure and user questions
2. ExecutionModule (Stage 2) - Generates and executes analysis code
3. ValidationModule (Stage 3) - Reviews and validates results

The SheetHero agent orchestrates these modules in an iterative loop:
Understanding → Execution → Validation → (feedback) → Execution...

Each module is self-contained, testable independently, and communicates via
dictionaries and strings for loose coupling.

"""

# Stage 1: Comprehension - Analyzes Excel structure and develops analysis plan
from .understanding import UnderstandingModule

# Stage 2: Execution - Generates and runs Python analysis code in sandbox
from .execution import ExecutionModule

# Stage 3: Validation - Reviews answers, provides feedback and confidence scores
from .validation import ValidationModule

# Public API - controls what imports when using: from modules import *
# Hides internal helpers while clearly exposing the three-stage architecture
__all__ = ["UnderstandingModule", "ExecutionModule", "ValidationModule"]

