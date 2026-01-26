"""SheetHero orchestrator class."""

import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from .runner import AgentRunner
from ..io.output_policy import OutputPolicy
from ...config.settings import Config
from ..io.context_builder import ExcelContextBuilder
from ...environment import Sandbox
from ...log.progress_logger import ProgressLogger
from ...stages.execution.stage import ExecutionStage
from ...stages.understanding.stage import UnderstandingStage
from ...stages.validation.stage import ValidationStage


class SheetHero:
    def __init__(self, excel_paths: Union[str, List[str]],
                 config: Config,
                 load_excel: bool = True):
        self.config = config
        self.excel_paths = excel_paths if isinstance(excel_paths, list) else [excel_paths]
        self.output_preferences = OutputPolicy.build_preferences(
            mode=self.config.output_mode,
            file_path=self.config.output_file
        )

        self.progress_logger = ProgressLogger(self.excel_paths)

        if self.output_preferences.get("mode") == "file":
            self._output_path = self.output_preferences.get("file_path")
        else:
            first_input = self.excel_paths[0] if self.excel_paths else "output"
            dir_path = os.path.dirname(first_input)
            base_name = os.path.splitext(os.path.basename(first_input))[0]
            self._output_path = os.path.join(dir_path, f"{base_name}_output.xlsx")

        self.output_instruction = self._build_output_instruction()

        if not self.config.api_key:
            raise ValueError("OpenAI API key is missing in Config")
        client_kwargs = {"api_key": self.config.api_key}
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        self.client = OpenAI(**client_kwargs)
        
        # initialize the sandbox
        self.sandbox = Sandbox(
            excel_paths=self.excel_paths,
            output_preferences=self.output_preferences,
            output_path=self._output_path,
            enabled_namespaces=["spreadsheet"],
            progress_logger=self.progress_logger,
            load_excel=load_excel
        )
        self.workbooks = self.sandbox.workbooks

        if load_excel:
            context_builder = ExcelContextBuilder(self.excel_paths, self.workbooks)
            self.excel_context_understanding = context_builder.build(
                self.config.total_token_budget * 2
            )
            self.excel_context_execution = context_builder.build(
                self.config.total_token_budget
            )
        else:
            self.excel_context_understanding = (
                "Excel file not loaded. Working with provided context only."
            )
            self.excel_context_execution = (
                "Excel file not loaded. Working with provided context only."
            )
        
        # initialize modules
        self.understanding_module = UnderstandingStage(
            self.client,
            self.config.deployment,
            self.excel_context_understanding
        )
        self.execution_module = ExecutionStage(
            self.client,
            self.config.deployment,
            self.sandbox,
            self.excel_context_execution,
            self.output_instruction,
            progress_log_file=self.progress_logger.file
        )
        self.validation_module = ValidationStage(
            self.client,
            self.config.deployment,
            self.excel_context_understanding,
            progress_log_file=self.progress_logger.file
        )
    
    # Run the agent
    def run(self, user_question: str) -> Dict[str, Any]:
        runner = AgentRunner(
            max_turns=self.config.max_turns,
            progress_logger=self.progress_logger
        )
        return runner.run(
            user_question,
            self.understanding_module,
            self.execution_module,
            self.validation_module
        )
    

    # Specify the rule of writing output
    def _build_output_instruction(self) -> str:
        """Generate AI instructions for output format based on user preferences."""
        mode = self.output_preferences.get("mode", "text")
        if mode == "file":
            return (
                "**OUTPUT REQUIREMENTS:**\n"
                f"1. Save final results to: `output_path` (variable available in code: \"{self._output_path}\")\n"
                "2. Use the UNIFIED OUTPUT WORKFLOW:\n"
                "   - Convert DataFrame to 2D list: `[df.columns.tolist()] + df.values.tolist()`\n"
                "   - Create output sheet: `create_output_sheet(\"Output\")`\n"
                "   - Write data: `write_dataframe_to_sheet(data_2d, \"Output\", \"A1\")`\n"
                "   - Add summary if needed: `add_summary_row(\"Output\", row_num, {\"Total\": val, \"Average\": avg})`\n"
                "   - Highlight important rows: `highlight_rows(\"Output\", [row_nums], {\"fill_color\": \"red\"})`\n"
                "   - Save: `save_workbook_to(output_path)`\n"
                "3. Return the saved file path in Final Answer\n"
                "4. DO NOT use DataFrame.to_excel() or pd.ExcelWriter()"
            )

        return (
            "Final results must be presented directly in the final answer as a clean markdown "
            "table or list. Do not save any files unless the user explicitly asks."
        )
