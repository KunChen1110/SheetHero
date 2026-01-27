"""Sandbox facade that builds execution state on init."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, Optional, Tuple

import matplotlib
import numpy as np
import openpyxl
import pandas as pd
from openpyxl.utils import column_index_from_string, get_column_letter, range_boundaries

from .runner import SandboxRunner
from ..spreadsheet.loader import load_world
from ..spreadsheet.namespace import SpreadsheetNamespace


class Sandbox:
    """Builds and holds sandbox execution state."""

    def __init__(self,
                 excel_paths: list[str],
                 output_preferences: Dict[str, Optional[str]],
                 output_path: str,
                 enabled_namespaces: Optional[list[str]] = None,
                 progress_logger=None,
                 load_excel: bool = True):
        self.excel_paths = excel_paths
        self.output_preferences = output_preferences
        self.output_path = output_path
        self.enabled_namespaces = enabled_namespaces or ["spreadsheet"]
        self.progress_logger = progress_logger

        self.code_globals = {
            "math": __import__("math"),
            "json": __import__("json"),
            "re": __import__("re"),
            "excel_paths": self.excel_paths,
            "output_preferences": self.output_preferences,
            "output_path": self.output_path,
            "namespaces": SimpleNamespace(),
        }
        self.code_locals = {}
        self.workbooks = {}
        self.runner = SandboxRunner()
        self.world = None

        if not load_excel:
            return

        matplotlib.use("Agg")

        self.world = load_world(self.excel_paths, self.output_path, self.progress_logger)
        self.workbooks = self.world.workbooks

        self.code_globals.update({
            "openpyxl": openpyxl,
            "workbooks": self.workbooks,
            "sheet_names": self.world.primary_workbook.sheetnames,
            "range_boundaries": range_boundaries,
            "get_column_letter": get_column_letter,
            "column_index_from_string": column_index_from_string,
            "pandas": pd,
            "pd": pd,
            "numpy": np,
            "np": np,
        })

        for namespace in self.enabled_namespaces:
            self.load_namespace(namespace)

    def load_namespace(self, name: str):
        """Load a namespace into the sandbox globals."""
        if name == "spreadsheet":
            if not self.world:
                raise RuntimeError("Cannot load namespaces without a loaded world.")
            namespace = SpreadsheetNamespace(self.world).build()
            self.code_globals["namespaces"].spreadsheet = namespace
            self.code_globals["spreadsheet"] = namespace
            self.code_globals.update(namespace.__dict__)
            return namespace

        raise ValueError(f"Unknown namespace: {name}")

    def run(self, code: str) -> dict:
        """Execute code in the sandbox and return the runner result."""
        return self.runner.run(code, self.code_globals, self.code_locals)
