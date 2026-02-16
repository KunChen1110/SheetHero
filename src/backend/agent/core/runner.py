"""Orchestration loop for iterative SheetHero execution."""

import time
from typing import Any, Dict

from ..io.report import RunReportBuilder
from ...stages.understanding.context_builder import ExcelContextBuilder
from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class AgentRunner:
    """Runs the Understanding -> Execution -> Validation loop."""

    def __init__(self, max_turns: int, progress_logger=None, token_budget: int = 50000):
        self.max_turns = max_turns
        self.progress_logger = progress_logger
        self.token_budget = token_budget

    def run(self, user_question: str, understanding_module, execution_module, validation_module) -> Dict[str, Any]:
        logger.info("Starting iterative three-stage analysis")
        if self.progress_logger:
            self.progress_logger.log(
                "🚀 [SheetHero] Starting iterative three-stage analysis...",
                to_terminal=False
            )
            self.progress_logger.log("=" * 80, to_terminal=False)

        overall_start_time = time.time()
        all_execution_results = []
        all_validation_results = []

        try:
            logger.info("Running understanding module")
            if self.progress_logger:
                self.progress_logger.log("📖 [STAGE 1] UNDERSTANDING MODULE", to_terminal=False)
                self.progress_logger.log("-" * 40, to_terminal=False)

            understanding_start_time = time.time()
            sandbox = execution_module.runner.sandbox
            understanding_context = ExcelContextBuilder(
                sandbox.excel_paths,
                sandbox.workbooks
            ).build(self.token_budget)
            understanding_output = understanding_module.run(
                user_question,
                understanding_context,
                None
            )
            understanding_duration = time.time() - understanding_start_time

            if self.progress_logger:
                self.progress_logger.log(
                    f"✅ [STAGE 1] Understanding completed in {understanding_duration:.2f}s",
                    to_terminal=False
                )
                self.progress_logger.log_raw(
                    f"\n**Understanding Analysis:**\n```\n{understanding_output}\n```\n"
                )

            overall_success = False
            final_answer = ""
            confidence_score = 0.0
            validation_passed = False

            for iteration in range(self.max_turns):
                logger.info(f"Starting iteration {iteration + 1}/{self.max_turns}")
                if self.progress_logger:
                    self.progress_logger.log(
                        f"\n🔄 [ITERATION {iteration + 1}/{self.max_turns}] EXECUTE-VALIDATE CYCLE",
                        to_terminal=False
                    )
                    self.progress_logger.log("=" * 60, to_terminal=False)

                if self.progress_logger:
                    self.progress_logger.log(
                        f"💻 [ITERATION {iteration + 1}] EXECUTION MODULE",
                        to_terminal=False
                    )
                    self.progress_logger.log("-" * 40, to_terminal=False)

                execution_start_time = time.time()

                sandbox = execution_module.runner.sandbox
                execution_context = ExcelContextBuilder(
                    sandbox.excel_paths,
                    sandbox.workbooks
                ).build(self.token_budget)
                if iteration > 0 and all_validation_results:
                    last_validation = all_validation_results[-1]
                    enhanced_understanding = understanding_module.enhance(
                        understanding_output,
                        last_validation
                    )
                else:
                    enhanced_understanding = understanding_output

                execution_result = execution_module.run(
                    user_query=user_question,
                    execution_context=execution_context,
                    understanding_output=enhanced_understanding
                )
                execution_duration = time.time() - execution_start_time
                all_execution_results.append(execution_result)

                status_emoji = "✅" if execution_result["success"] else "❌"
                if self.progress_logger:
                    self.progress_logger.log(
                        f"{status_emoji} [ITERATION {iteration + 1}] Execution completed in {execution_duration:.2f}s",
                        to_terminal=False
                    )
                    self.progress_logger.log(
                        f"🔄 [ITERATION {iteration + 1}] Total turns: {execution_result['total_turns']}",
                        to_terminal=False
                    )
                    self.progress_logger.log(
                        f"📊 [ITERATION {iteration + 1}] Code executions: "
                        f"{execution_result.get('execution_summary', {}).get('total_code_executions', 0)}",
                        to_terminal=False
                    )

                logger.info(f"Running validation module for iteration {iteration + 1}")
                if self.progress_logger:
                    self.progress_logger.log(
                        f"\n🔍 [ITERATION {iteration + 1}] VALIDATION MODULE",
                        to_terminal=False
                    )
                    self.progress_logger.log("-" * 40, to_terminal=False)

                validation_start_time = time.time()
                validation_result = validation_module.run(
                    execution_result=execution_result,
                    user_query=user_question,
                    understanding_output=understanding_output,
                    execution_context=execution_context
                )
                validation_duration = time.time() - validation_start_time
                all_validation_results.append(validation_result)

                validation_emoji = "✅" if validation_result["validation_passed"] else "⚠️"
                if self.progress_logger:
                    self.progress_logger.log(
                        f"{validation_emoji} [ITERATION {iteration + 1}] Validation completed in {validation_duration:.2f}s",
                        to_terminal=False
                    )
                    self.progress_logger.log(
                        f"🎯 [ITERATION {iteration + 1}] Confidence: {validation_result['confidence_score']:.2f}",
                        to_terminal=False
                    )
                    self.progress_logger.log(
                        f"📋 [ITERATION {iteration + 1}] Validation: "
                        f"{'PASSED' if validation_result['validation_passed'] else 'FAILED'}",
                        to_terminal=False
                    )

                if validation_result['validation_passed']:
                    logger.info(f"Validation passed on iteration {iteration + 1}")
                    if self.progress_logger:
                        self.progress_logger.log(
                            f"🎉 [SUCCESS] Validation passed on iteration {iteration + 1}!",
                            to_terminal=False
                        )
                    final_answer = validation_result.get('verified_answer', execution_result['answer'])
                    overall_success = True
                    confidence_score = validation_result['confidence_score']
                    validation_passed = True
                    break

                if not validation_result.get('requires_reexecution', True):
                    logger.warning("Validation indicates no further improvement possible")
                    if self.progress_logger:
                        self.progress_logger.log(
                            "🛑 [STOPPING] Validation indicates no further improvement possible",
                            to_terminal=False
                        )
                    final_answer = execution_result['answer']
                    overall_success = False
                    confidence_score = validation_result['confidence_score']
                    validation_passed = False
                    break

                logger.info(f"Issues found, preparing for iteration {iteration + 2}")
                if self.progress_logger:
                    self.progress_logger.log(
                        f"🔄 [CONTINUE] Issues found, preparing for iteration {iteration + 2}",
                        to_terminal=False
                    )

                    if validation_result.get('issues_found'):
                        self.progress_logger.log_raw("\n**Issues Found:**\n")
                        for issue in validation_result['issues_found']:
                            self.progress_logger.log_raw(f"- {issue}\n")
                    if validation_result.get('improvement_feedback'):
                        self.progress_logger.log_raw(
                            f"\n**Improvement Feedback:**\n```\n{validation_result['improvement_feedback']}\n```\n"
                        )

                if iteration == self.max_turns - 1:
                    logger.warning("Reached maximum iterations without validation")
                    if self.progress_logger:
                        self.progress_logger.log(
                            "⚠️ [MAX ITERATIONS] Reached maximum iterations without validation",
                            to_terminal=False
                        )
                    final_answer = execution_result['answer']
                    overall_success = False
                    confidence_score = validation_result['confidence_score']
                    validation_passed = False

            return RunReportBuilder.build_success_result(
                all_execution_results=all_execution_results,
                all_validation_results=all_validation_results,
                overall_start_time=overall_start_time,
                final_answer=final_answer,
                overall_success=overall_success,
                confidence_score=confidence_score,
                validation_passed=validation_passed,
                user_question=user_question,
                understanding_output=understanding_output,
                progress_logger=self.progress_logger
            )

        except Exception as e:
            return RunReportBuilder.build_error_result(
                all_execution_results=all_execution_results,
                all_validation_results=all_validation_results,
                overall_start_time=overall_start_time,
                error=e,
                user_question=user_question,
                progress_logger=self.progress_logger
            )
