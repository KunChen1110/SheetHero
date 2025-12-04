"""
SheetHero Core Package
=======================

Main entry point for SheetHero functionality.

This package initializer allows clean imports:
    from core import SheetHero
    from core import build_output_preferences

Instead of the more verbose:
    from core.agent import SheetHero
    from core.agent import build_output_preferences
"""

from .agent import SheetHero, build_output_preferences, output_mode

# Public API - defines what gets imported with `from core import *`
# Explicitly controls exposure of internal implementation details
__all__ = ["SheetHero", "build_output_preferences", "output_mode"]