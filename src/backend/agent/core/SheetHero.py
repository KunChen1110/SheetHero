"""SheetHero orchestrator class."""

import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from .runner import AgentRunner
from ..io.output_policy import OutputPolicy
from ...config.settings import Config
from ...environment import Sandbox
from ...log.progress_logger import ProgressLogger
from ...stages.execution.stage import ExecutionStage
from ...stages.qa.stage import QualityAssuranceStage
from ...stages.cleaning.stage import DataCleaningStage
from ...stages.diagnose.stage import DiagnoseStage
from ...stages.understanding.stage import UnderstandingStage
from ...stages.understanding.context_builder import ExcelContextBuilder
from ...stages.validation.stage import ValidationStage
from .session import SheetHeroSession


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
            base_name = os.path.splitext(os.path.basename(first_input))[0]
            task_dir = os.path.basename(os.path.dirname(first_input)) or "output"
            artifacts_dir = os.path.join(
                "/home/scygl3/GRP/team29_project",
                "artifacts",
                task_dir
            )
            os.makedirs(artifacts_dir, exist_ok=True)
            self._output_path = os.path.join(artifacts_dir, f"{base_name}_output.xlsx")

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

        # initialize modules
        self.understanding_module = UnderstandingStage(
            self.client,
            self.config.deployment,
            progress_logger=self.progress_logger
        )
        self.diagnose_module = DiagnoseStage(
            self.client,
            self.config.deployment,
            self.excel_paths,
            sandbox=self.sandbox,
            token_budget=self.config.total_token_budget,
            progress_logger=self.progress_logger
        )
        self.execution_module = ExecutionStage(
            self.client,
            self.config.deployment,
            self.sandbox,
            self.output_instruction,
            progress_log_file=self.progress_logger.file
        )
        self.validation_module = ValidationStage(
            self.client,
            self.config.deployment,
            "",
            progress_log_file=self.progress_logger.file
        )
        self.qa_module = QualityAssuranceStage(
            self.client,
            self.config.deployment,
            progress_logger=self.progress_logger
        )
        self.qa_module.max_qa_rounds = self.config.max_qa_rounds
        self.cleaning_module = DataCleaningStage(
            self.client,
            self.config.deployment,
            token_budget=self.config.total_token_budget,
            progress_logger=self.progress_logger
        )
        self._qa_sessions = {}
    
    # Run the agent
    def run(self, user_question: str) -> Dict[str, Any]:
        runner = AgentRunner(
            max_turns=self.config.max_turns,
            progress_logger=self.progress_logger,
            token_budget=self.config.total_token_budget
        )
        return runner.run(
            user_question,
            self.understanding_module,
            self.execution_module,
            self.validation_module
        )

    def start_session(self, user_question: str) -> SheetHeroSession:
        return SheetHeroSession(original_query=user_question)

    def step(self, session: SheetHeroSession, user_input: Optional[str] = None) -> Dict[str, Any]:
        qa_stage = self._qa_sessions.get(session.session_id)

        # ========== INIT ==========
        if session.state == "init":
            understanding_context = ExcelContextBuilder(
                self.excel_paths,
                self.sandbox.workbooks
            ).build(self.config.total_token_budget)
            session.understanding = self.understanding_module.run(
                session.original_query,
                understanding_context
            )
            wb_view = self.sandbox.get_workbook_view()
            question_list = self.diagnose_module.run_readonly(
                workbooks=wb_view,
                user_task=session.original_query
            )

            qa_stage = QualityAssuranceStage(
                self.client,
                self.config.deployment,
                progress_logger=self.progress_logger
            )
            qa_stage.max_qa_rounds = self.config.max_qa_rounds
            qa_stage.start(question_list=question_list, original_question=session.original_query)
            self._qa_sessions[session.session_id] = qa_stage

            question = qa_stage.next_question()
            if question:
                session.state = "qa"
                return {"type": "clarification", "message": question}

            qa_stage.finalize_decision()
            cleaning_actions = qa_stage.export_cleaning_actions()
            session.state = "cleaning"
            return {"type": "progress", "stage": "cleaning"}

        # ========== QA ==========
        if session.state == "qa":
            if user_input is None:
                return {"type": "clarification", "message": "Please clarify your request."}

            qa_stage = qa_stage or self._qa_sessions.get(session.session_id)
            if qa_stage is None:
                return {"type": "error", "message": "QA session not initialized."}

            qa_stage.consume_user_reply(user_input)
            if qa_stage.get_last_mismatch():
                followup = qa_stage.next_question()
                hint = qa_stage.get_last_mismatch()
                if followup:
                    return {
                        "type": "clarification",
                        "message": f"{hint}\n\nPlease answer this question:\n{followup}",
                    }
                qa_stage.clear_last_mismatch()
            question = qa_stage.next_question()
            if question:
                return {"type": "clarification", "message": question}

            qa_stage.finalize_decision()
            cleaning_actions = qa_stage.export_cleaning_actions()
            session.state = "cleaning"
            return {"type": "progress", "stage": "cleaning"}

        # ========== CLEANING ==========
        if session.state == "cleaning":
            self.cleaning_module.apply(
                sandbox=self.sandbox,
                actions=qa_stage.export_cleaning_actions() if qa_stage else []
            )
            if qa_stage:
                qa_stage.clear_cleaning_actions()
            if self.cleaning_module.last_run_affects_schema():
                understanding_context = ExcelContextBuilder(
                    self.excel_paths,
                    self.sandbox.workbooks
                ).build(self.config.total_token_budget)
                session.understanding = self.understanding_module.run(
                    session.original_query,
                    understanding_context
                )
            session.state = "executing"
            return {"type": "progress", "stage": "executing"}

        # ========== EXECUTING ==========
        if session.state == "executing":
            understanding_output = session.understanding
            if not understanding_output:
                return {"type": "error", "message": "Understanding missing before execution."}
            user_query = session.original_query
            execution_context = ExcelContextBuilder(
                self.excel_paths,
                self.sandbox.workbooks
            ).build(self.config.total_token_budget)
            execution_result = self.execution_module.run(
                user_query=user_query,
                execution_context=execution_context,
                understanding_output=understanding_output
            )
            validation_result = self.validation_module.run(
                execution_result=execution_result,
                user_query=user_query,
                understanding_output=understanding_output,
                execution_context=execution_context
            )

            session.result = {
                "execution_result": execution_result,
                "validation_result": validation_result,
                "final_answer": validation_result.get(
                    "verified_answer",
                    execution_result.get("answer", "")
                )
            }

            # Validation succeeds
            if validation_result.get("validation_passed"):
                session.state = "done"
            else:
            # Validation fails
                if not validation_result.get("requires_reexecution", True):
                    session.state = "done"
                else:
                    session.understanding = self.understanding_module.enhance(
                        session.understanding,
                        validation_result
                    )
                    session.state = "executing"
                    return {"type": "progress", "stage": "executing"}
            self._qa_sessions.pop(session.session_id, None)
            self._log_final_report(session)
            return {"type": "final", "result": session.result}

        if session.state == "done":
            return {"type": "final", "result": session.result}

        return {"type": "error", "message": f"Unknown session state: {session.state}"}

    def _log_final_report(self, session: SheetHeroSession) -> None:
        if not self.progress_logger:
            return

        exec_result = (session.result or {}).get("execution_result", {})
        val_result = (session.result or {}).get("validation_result", {})

        self.progress_logger.log("\n" + "=" * 80, to_terminal=False)
        self.progress_logger.log("🎯 [FINAL SUMMARY]", to_terminal=False)
        self.progress_logger.log("=" * 80, to_terminal=False)
        self.progress_logger.log(
            f"Success: {'✅ YES' if exec_result.get('success') else '❌ NO'}",
            to_terminal=False
        )
        self.progress_logger.log(
            f"Validation Passed: {'✅ YES' if val_result.get('validation_passed') else '❌ NO'}",
            to_terminal=False
        )
        self.progress_logger.log(
            f"Confidence Score: {val_result.get('confidence_score', 0.0):.2f}/1.0",
            to_terminal=False
        )
        self.progress_logger.log(
            f"Final Answer: {exec_result.get('answer', '')}",
            to_terminal=False
        )
        self.progress_logger.log("=" * 80, to_terminal=False)
    

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

    @staticmethod
    def _build_clarification_message(result: Dict[str, Any]) -> str:
        feedback = (result.get("improvement_feedback") or "").strip()
        issues = result.get("issues_found") or []

        lines = ["I need a bit more detail to continue."]
        if feedback:
            lines.append(feedback)
        if issues:
            lines.append("Issues detected:")
            for issue in issues:
                lines.append(f"- {issue}")
        lines.append("Please clarify or provide additional context.")
        return "\n".join(lines)
