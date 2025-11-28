"""
 * File: __init__.py (Core Module)
 * ----------------------------------
 * Package initialization file for the SheetBrain core module.
 *
 * This file sits in the 'core/' directory and serves a crucial role:
 * it transforms the directory into an importable Python package and provides
 * a clean, convenient way for users to access the main SheetBrain class.
 *
 * Purpose of this file:
 * =====================
 * 1. **Package Marker**: Tells Python "this directory is a package"
 * 2. **Convenient Imports**: Allows users to import SheetBrain directly from 'core'
 * 3. **API Definition**: Explicitly declares what this package exposes publicly
 *
 * Without this file, users would have to type:
 *     from core.agent import SheetBrain
 *
 * With this file, they can use the cleaner:
 *     from core import SheetBrain
 *
 * This pattern is standard in Python libraries - it makes APIs more ergonomic.
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

# Import the main SheetBrain class from the agent module in this package
# The dot (.) before 'agent' means "look in the current package"
# This is a relative import - it only works inside a package
from .agent import SheetBrain, build_output_preferences, output_mode

# __all__ defines the public API of this package
# This special variable controls what gets imported when someone uses:
#     from core import *
#
# Why this matters:
# - **Clarity**: Explicitly states what's meant to be public vs. private
# - **Control**: Prevents accidental exposure of internal modules (agent, utils, etc.)
# - **Documentation**: Acts as a self-documenting list of the package's main exports
# - **IDE Support**: Helps IDEs know what to suggest in autocomplete
#
# In this case, we're saying: "The only thing we want to expose from the core
# package is the SheetBrain class - everything else is implementation detail."
__all__ = ["SheetBrain", "build_output_preferences", "output_mode"]

# === Architecture Note ===
# This structure follows a layered architecture pattern:
#
# config/          # Configuration layer (settings, API keys)
# core/            # Core business logic (THIS FILE)
#     __init__.py  #   - Package initializer (you are here)
#     agent.py     #   - Main orchestration
#     modules/     #   - Analysis stages (understand, execute, validate)
# utils/           # Utility layer (helpers, tools)
# main.py          # CLI entry point
# run_example.py   # Example usage
#
# Having this __init__.py means users can treat 'core' as a unified package
# rather than worrying about its internal file structure.
#
# === Best Practice Tip ===
# For small packages, __init__.py is minimal like this. For larger ones, it might:
# - Import multiple key classes
# - Define package-level version info: __version__ = "1.0.0"
# - Set up package-wide logging
# - Check dependencies on import
#
# Keep it simple - only import what's truly part of the package's public API.