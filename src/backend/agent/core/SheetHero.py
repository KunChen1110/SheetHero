"""SheetHero orchestrator class."""
import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI
import openpyxl
import pandas as pd
import numpy as np
from openpyxl.utils import column_index_from_string, get_column_letter, range_boundaries

from .runner import AgentRunner
from ..io.output_policy import OutputPolicy
from ...config.settings import Config
from ...environment import Sandbox
from ...environment.spreadsheet.world import SpreadsheetWorld
from ...log.progress_logger import ProgressLogger
from ...stages.execution.stage import ExecutionStage
from ...stages.qa.stage import QualityAssuranceStage
from ...stages.cleaning.stage import DataCleaningStage
from ...stages.diagnose.stage import DiagnoseStage
from ...router.diagnose_router import DiagnoseRouter
from ...stages.interact.stage import InteractStage
from ...stages.understanding.stage import UnderstandingStage
from ...stages.understanding.context_builder import ExcelContextBuilder
from ...stages.validation.stage import ValidationStage
from .session import SheetHeroSession
from ..utils.context_extractor import ContextExtractor


class SheetHero:
    def __init__(self, excel_paths: Union[str, List[str]],
                 config: Config,
                 load_excel: bool = True):
        self.config = config
        raw_paths = excel_paths if isinstance(excel_paths, list) else [excel_paths]
        self.excel_paths = [p for p in raw_paths if p]
        self.has_excel = len(self.excel_paths) > 0
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
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../../..")
            )
            artifacts_dir = os.path.join(
                project_root,
                "artifacts",
                task_dir
            )
            os.makedirs(artifacts_dir, exist_ok=True)
            self._output_path = os.path.join(artifacts_dir, f"{base_name}_output.xlsx")
        self._output_existed_before = os.path.exists(self._output_path)

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
            enabled_namespaces=["spreadsheet"] if self.has_excel else [],
            progress_logger=self.progress_logger,
            load_excel=load_excel and self.has_excel
        )
        self.workbooks = self.sandbox.workbooks

        # initialize modules
        self.understanding_module = UnderstandingStage(
            self.client,
            self.config.deployment,
            progress_logger=self.progress_logger
        )
        self.interact_module = InteractStage(
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
        self.diagnose_router = DiagnoseRouter(
            self.client,
            self.config.deployment,
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
        if not self.has_excel:
            response = self.interact_module.run(user_question)
            return {
                "type": "final",
                "result": {"final_answer": response},
                "message": response,
            }
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
        current_request = user_input if user_input is not None else session.original_query
    
        self._log_session_context(session, current_request)

        # ========== INIT ==========
        if session.state == "init":
            init_result = self._handle_init(session, current_request)
            if init_result is not None:
                return init_result

        # ========== UNDERSTANDING ==========
        if session.state == "understanding":
            return self._handle_understanding(session, current_request)

        # ========== DIAGNOSING ==========
        if session.state == "diagnosing":
            return self._handle_diagnosing(session, current_request)

        # ========== QA ==========
        if session.state == "qa":
            if user_input is None:
                return {"type": "clarification", "stage": "qa", "message": "Please clarify your request."}

            return self._handle_qa(session, user_input, qa_stage)

        # ========== CLEANING ==========
        if session.state == "cleaning":
            return self._handle_cleaning(session, qa_stage, current_request)

        # ========== EXECUTING ==========
        if session.state == "executing":
            return self._handle_execution(session, current_request)

        # ========== VALIDATION ==========
        if session.state == "validation":
            return self._handle_validation(session, current_request)

        if session.state == "done":
            return {"type": "final", "result": session.result}

        return {"type": "error", "message": f"Unknown session state: {session.state}"}

    def _log_session_context(self, session: SheetHeroSession, current_request: str) -> None:
        if not self.progress_logger:
            return
        context = (session.context_understanding or "").strip() or "<empty>"
        current_wb_summary = self._summarize_workbooks(session.current_workbooks)
        previous_wb_summary = self._summarize_workbooks(session.previous_workbooks)
        safe_request = (current_request or "").replace("`", "'").strip() or "<empty>"
        self.progress_logger.log_raw(
            "\n### [SESSION CONTEXT]\n"
            f"- state: `{session.state}`\n"
            f"- request: `{safe_request}`\n"
            f"- context_understanding:\n```\n{context}\n```\n"
            f"- current_workbooks: `{current_wb_summary}`\n"
            f"- previous_workbooks: `{previous_wb_summary}`\n"
        )

    @staticmethod
    def _summarize_workbooks(workbooks: Optional[object]) -> str:
        if workbooks is None:
            return "none"
        if isinstance(workbooks, dict):
            keys = list(workbooks.keys())
            preview = ", ".join(str(k) for k in keys[:5])
            more = " ..." if len(keys) > 5 else ""
            return f"{len(keys)} workbook(s): {preview}{more}"
        if isinstance(workbooks, (list, tuple)):
            return f"{len(workbooks)} workbook(s)"
        return type(workbooks).__name__

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

    def _handle_init(self, session: SheetHeroSession, current_request: str) -> Optional[Dict[str, Any]]:
        active_workbooks = session.get_active_workbooks()

        if not active_workbooks and self.has_excel:
            active_workbooks = self.sandbox.workbooks
            session.current_workbooks = active_workbooks

        if not active_workbooks:
            needs_spreadsheet = self.interact_module.needs_spreadsheet(current_request)
            if not needs_spreadsheet:
                if self.progress_logger:
                    self.progress_logger.log(
                        "[INTERACT] case=1 no_spreadsheet_needed",
                        to_terminal=False
                    )
                response = self.interact_module.run(current_request)
                session.understanding = response
                session.result = {"final_answer": response}
                session.state = "done"
                return {"type": "final", "result": session.result, "message": response}

            if session.previous_workbooks:
                matches_context = self.interact_module.context_matches(
                    current_request,
                    session.context_understanding or ""
                )
                if matches_context:
                    session.current_workbooks = session.previous_workbooks
                    active_workbooks = session.current_workbooks
                else:
                    session.context_understanding = self.interact_module.summarize_context(
                        current_request
                    )
                    if self.progress_logger:
                        self.progress_logger.log(
                            f"[INTERACT] case=3 context_mismatch context=\"{session.context_understanding}\"",
                            to_terminal=False
                        )
                    message = (
                        "Your request seems to switch to a different analysis topic. "
                        "Please confirm whether to switch Excel files, or upload a new Excel file."
                    )
                    session.result = {"final_answer": message}
                    session.state = "done"
                    return {"type": "final", "result": session.result, "message": message}

            if not active_workbooks:
                session.context_understanding = self.interact_module.summarize_context(
                    current_request
                )
                if self.progress_logger:
                    self.progress_logger.log(
                        f"[INTERACT] case=2 needs_spreadsheet_missing_workbook context=\"{session.context_understanding}\"",
                        to_terminal=False
                    )
                message = "Excel needed, please upload excel"
                session.result = {"final_answer": message}
                session.state = "done"
                return {"type": "final", "result": session.result, "message": message}
        if self.progress_logger:
            self.progress_logger.log(
                f"[INTERACT] case=4 proceed_with_workbook context=\"{(session.context_understanding or '').strip()}\"",
                to_terminal=False
            )
        self._hydrate_sandbox_from_session(active_workbooks)
        session.current_workbooks = active_workbooks

        session.state = "understanding"
        return {"type": "progress", "stage": "understanding"}

    def _handle_understanding(self, session: SheetHeroSession, current_request: str) -> Dict[str, Any]:
        active_workbooks = session.get_active_workbooks()
        excel_context = ExcelContextBuilder(
            self._get_context_paths(session),
            active_workbooks
        ).build(self.config.total_token_budget)

        self._append_ui_thought(session, "understanding", "running", "Understanding workbook/task context")
        session.understanding = self.understanding_module.run(
            current_request,
            excel_context,
            session.context_understanding
        )
        self._append_ui_thought(session, "understanding", "done", session.understanding or "")
        session.state = "diagnosing"
        return {"type": "progress", "stage": "diagnosing"}

    def _handle_diagnosing(self, session: SheetHeroSession, current_request: str) -> Dict[str, Any]:
        wb_view = self.sandbox.get_workbook_view()
        decision = self.diagnose_router.decide(
            user_question=current_request,
            understanding_output=session.understanding or "",
            workbook_view=wb_view
        )

        if decision.should_diagnose:
            self._append_ui_thought(session, "diagnosing", "running", "Diagnosing data quality risks")
            question_list = self.diagnose_module.run_readonly(
                workbooks=wb_view,
                user_task=current_request
            )
            self._append_ui_thought(session, "diagnosing", "done", question_list)

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
                return {"type": "clarification", "stage": "qa", "message": question}

            qa_stage.finalize_decision()
            session.state = "cleaning"
            return {"type": "progress", "stage": "cleaning"}

        self._append_ui_thought(
            session,
            "diagnosing",
            "skipped",
            "No blocking data quality clarification required"
        )
        session.state = "executing"
        return {"type": "progress", "stage": "executing"}

    def _handle_qa(self, session: SheetHeroSession, user_input: str,
                   qa_stage: Optional[QualityAssuranceStage]) -> Dict[str, Any]:
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
                    "stage": "qa",
                    "message": f"{hint}\n\nPlease answer this question:\n{followup}",
                }
            qa_stage.clear_last_mismatch()
        question = qa_stage.next_question()
        if question:
            return {"type": "clarification", "stage": "qa", "message": question}

        qa_stage.finalize_decision()
        session.state = "cleaning"
        return {"type": "progress", "stage": "cleaning"}

    def _handle_cleaning(self, session: SheetHeroSession,
                         qa_stage: Optional[QualityAssuranceStage],
                         current_request: str) -> Dict[str, Any]:
        actions = qa_stage.export_cleaning_actions() if qa_stage else []
        self._append_ui_thought(session, "cleaning", "running", actions)
        self.cleaning_module.apply(
            sandbox=self.sandbox,
            actions=actions
        )
        self._append_ui_thought(session, "cleaning", "done", actions)
        if qa_stage:
            qa_stage.clear_cleaning_actions()
        session.state = "executing"
        return {"type": "progress", "stage": "executing"}

    def _handle_execution(self, session: SheetHeroSession,
                          current_request: str) -> Dict[str, Any]:
        understanding_output = session.understanding
        if not understanding_output:
            return {"type": "error", "message": "Understanding missing before execution."}
        user_query = current_request
        active_workbooks = session.get_active_workbooks()
        execution_context = ExcelContextBuilder(
            self._get_context_paths(session),
            active_workbooks
        ).build(self.config.total_token_budget)
        self._append_ui_thought(session, "executing", "running", "Generating and running execution code")
        execution_result = self.execution_module.run(
            user_query=user_query,
            execution_context=execution_context,
            understanding_output=understanding_output
        )
        self._append_ui_thought(
            session,
            "executing",
            "done",
            {
                "success": execution_result.get("success"),
                "answer": execution_result.get("answer"),
                "total_turns": execution_result.get("total_turns"),
            },
        )
        session.pending_execution_result = execution_result
        session.pending_execution_context = execution_context
        session.state = "validation"
        return {"type": "progress", "stage": "validation"}

    def _handle_validation(self, session: SheetHeroSession,
                           current_request: str) -> Dict[str, Any]:
        execution_result = session.pending_execution_result
        execution_context = session.pending_execution_context
        if not execution_result or execution_context is None:
            return {"type": "error", "message": "Execution result missing before validation."}
        understanding_output = session.understanding or ""
        user_query = current_request

        self._append_ui_thought(session, "validation", "running", "Validating execution result")
        validation_result = self.validation_module.run(
            execution_result=execution_result,
            user_query=user_query,
            understanding_output=understanding_output,
            execution_context=execution_context
        )
        self._append_ui_thought(
            session,
            "validation",
            "done",
            {
                "validation_passed": validation_result.get("validation_passed"),
                "confidence_score": validation_result.get("confidence_score"),
                "requires_reexecution": validation_result.get("requires_reexecution"),
                "issues_found": validation_result.get("issues_found", []),
            },
        )

        session.result = {
            "execution_result": execution_result,
            "validation_result": validation_result,
            "final_answer": validation_result.get(
                "verified_answer",
                execution_result.get("answer", "")
            ),
            "edited_existing_file": self._output_existed_before,
        }

        extracted_context = ContextExtractor.extract_workbook_purpose_domain(
            session.understanding or ""
        ).strip()
        if extracted_context:
            session.context_understanding = extracted_context

        if validation_result.get("validation_passed"):
            session.state = "done"
        else:
            if not validation_result.get("requires_reexecution", True):
                session.state = "done"
            else:
                session.understanding = self.understanding_module.enhance(
                    session.understanding,
                    validation_result
                )
                session.state = "executing"
                return {"type": "progress", "stage": "executing"}
        session.pending_execution_result = None
        session.pending_execution_context = None
        self._qa_sessions.pop(session.session_id, None)
        self._log_final_report(session)
        return {"type": "final", "result": session.result}

    @staticmethod
    def _append_ui_thought(
        session: SheetHeroSession,
        stage: str,
        status: str,
        content: Any,
    ) -> None:
        session.ui_thoughts.append(
            {
                "stage": stage,
                "status": status,
                "content": content,
            }
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

    def _get_context_paths(self, session: SheetHeroSession) -> List[str]:
        active_workbooks = session.get_active_workbooks()
        if active_workbooks:
            return list(active_workbooks.keys())
        if self.excel_paths:
            return self.excel_paths
        return []

    def _hydrate_sandbox_from_session(self, workbooks: Dict[str, Any]) -> None:
        if not workbooks:
            return
        primary_path = next(iter(workbooks.keys()))
        self.sandbox.workbooks = workbooks
        self.sandbox.world = SpreadsheetWorld(
            workbooks=workbooks,
            output_path=self.sandbox.output_path,
            primary_path=primary_path
        )
        self.sandbox.code_globals.update({
            "openpyxl": openpyxl,
            "workbooks": workbooks,
            "sheet_names": self.sandbox.world.primary_workbook.sheetnames,
            "range_boundaries": range_boundaries,
            "get_column_letter": get_column_letter,
            "column_index_from_string": column_index_from_string,
            "pandas": pd,
            "pd": pd,
            "numpy": np,
            "np": np,
        })
        self.sandbox.load_namespace("spreadsheet")

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
