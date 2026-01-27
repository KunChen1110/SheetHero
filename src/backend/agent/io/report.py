"""Report building for iterative agent runs."""

import time
from typing import Any, Dict, List, Optional

from ...log.logger_registry import LoggerRegistry

logger = LoggerRegistry.setup_logger(__name__)


class RunReportBuilder:
    """Builds final results and logging summaries for runs."""

    @staticmethod
    def build_conversation_histories(all_execution_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        all_conversation_histories = []
        for exec_result in all_execution_results:
            conv_history = exec_result.get('conversation_history', [])
            if conv_history:
                all_conversation_histories.append({
                    'iteration': all_execution_results.index(exec_result) + 1,
                    'conversation_history': conv_history
                })
        return all_conversation_histories

    @staticmethod
    def build_success_result(
        all_execution_results: List[Dict[str, Any]],
        all_validation_results: List[Dict[str, Any]],
        overall_start_time: float,
        final_answer: str,
        overall_success: bool,
        confidence_score: float,
        validation_passed: bool,
        user_question: str,
        understanding_output: str,
        progress_logger=None
    ) -> Dict[str, Any]:
        if all_validation_results:
            final_validation = all_validation_results[-1]
            issues_found = final_validation.get('issues_found', [])
            improvement_feedback = final_validation.get('improvement_feedback', '')
        else:
            issues_found = []
            improvement_feedback = ''

        all_conversation_histories = RunReportBuilder.build_conversation_histories(
            all_execution_results
        )

        total_duration = time.time() - overall_start_time
        total_iterations = len(all_execution_results)

        logger.info(
            f"Analysis completed. Success: {overall_success}, Iterations: {total_iterations}"
        )
        if progress_logger:
            progress_logger.log("\n" + "=" * 80, to_terminal=False)
            progress_logger.log("🎯 [FINAL SUMMARY]", to_terminal=False)
            progress_logger.log("=" * 80, to_terminal=False)
            progress_logger.log(
                f"Overall Success: {'✅ YES' if overall_success else '❌ NO'}",
                to_terminal=False
            )
            progress_logger.log(f"Total Iterations: {total_iterations}", to_terminal=False)
            progress_logger.log(f"Final Answer: {final_answer}", to_terminal=False)
            progress_logger.log(
                f"Confidence Score: {confidence_score:.2f}/1.0",
                to_terminal=False
            )
            progress_logger.log(
                f"Validation Passed: {'✅ YES' if validation_passed else '❌ NO'}",
                to_terminal=False
            )
            progress_logger.log(
                f"Total Duration: {total_duration:.2f}s",
                to_terminal=False
            )
            progress_logger.log("=" * 80, to_terminal=False)

        progress_log_path = None
        if progress_logger:
            progress_log_path = progress_logger.close()

        result = {
            "success": overall_success,
            "answer": final_answer,
            "confidence_score": confidence_score,
            "validation_passed": validation_passed,
            "total_iterations": total_iterations,
            "all_execution_results": all_execution_results,
            "all_validation_results": all_validation_results,
            "conversation_history": all_conversation_histories,
            "issues_found": issues_found,
            "improvement_feedback": improvement_feedback,
            "total_duration": total_duration,
            "user_question": user_question,
            "understanding_output": understanding_output
        }

        if progress_log_path:
            result["verbose_log_path"] = progress_log_path

        return result

    @staticmethod
    def build_error_result(
        all_execution_results: List[Dict[str, Any]],
        all_validation_results: List[Dict[str, Any]],
        overall_start_time: float,
        error: Exception,
        user_question: str,
        progress_logger=None
    ) -> Dict[str, Any]:
        error_duration = time.time() - overall_start_time
        logger.error(f"Critical error: {str(error)}")

        if progress_logger:
            progress_logger.log(
                f"❌ [SheetHero] Critical error: {str(error)}",
                to_terminal=False
            )
            progress_logger.log(
                f"⏱️ [SheetHero] Failed after {error_duration:.2f}s",
                to_terminal=False
            )

        progress_log_path = None
        if progress_logger:
            progress_log_path = progress_logger.close()

        all_conversation_histories = RunReportBuilder.build_conversation_histories(
            all_execution_results
        )

        result = {
            "success": False,
            "answer": f"Analysis failed due to error: {str(error)}",
            "confidence_score": 0.0,
            "validation_passed": False,
            "total_iterations": len(all_execution_results),
            "all_execution_results": all_execution_results,
            "all_validation_results": all_validation_results,
            "conversation_history": all_conversation_histories,
            "issues_found": [f"Critical error: {str(error)}"],
            "improvement_feedback": "Review the error and try again",
            "total_duration": error_duration,
            "user_question": user_question
        }

        if progress_log_path:
            result["verbose_log_path"] = progress_log_path

        return result
