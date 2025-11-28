"""
 * Package initialization file for the SheetBrain configuration module.
 *
 * This file turns the 'config' directory into a proper Python package that can
 * be imported. Even when empty, its presence tells Python "this folder is a package."
 *
 * What this file does:
 * 1. Imports key classes so users can access them easily
 * 2. Defines the public API of the package (what's visible to outsiders)
 * 3. Runs any setup code when the package is first imported
 *
 * Key Concept - Convenience Imports:
 * Without this file, users would have to type:
 *     from config.settings import Config
 *
 * With this file, they can type the cleaner:
 *     from config import Config
 *
 * This is a common Python pattern to make APIs more user-friendly.
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

# Import the Config class from the settings module within this package
# The dot (.) before 'settings' means "look in the current package directory"
# This makes Config available directly when someone imports the config package
# Example: from config import Config  (instead of from config.settings import Config)
from .settings import Config

# __all__ defines the public API of this package
# It controls what gets imported when someone uses: from config import *
#
# Why this matters:
# - Explicitly declares what is meant to be public vs. private
# - Prevents accidental exposure of internal helper functions
# - Acts as self-documenting code: tells developers what's important
#
# Here, we're saying: "The only thing we want to expose from this package is Config"
__all__ = ["Config"]

# === Best Practice Note ===
# For simple packages like this, __init__.py is minimal. But it can also contain:
# - Package-level docstrings (like above)
# - Version information (__version__ = "1.0.0")
# - Conditional imports (try/except for optional dependencies)
# - Package-level utility functions
# - Logging setup for the entire package
#
# The key rule: keep it simple and only put things here that truly belong to the
# package as a whole, not to individual modules.