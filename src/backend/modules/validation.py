# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Validation module for final quality assurance after execution."""

import re
import time
from typing import Dict, Any, Optional

from utils.logger import setup_logger
from modules.prompts import build_validation_prompt

logger = setup_logger(__name__)


class ValidationModule:
    """
    Module responsible for final quality assurance after ExecutionModule completes its multi-turn process.
    If issues are found, provides feedback for re-execution. If validation passes, confirms the final answer.
    """

    def __init__(self, client, deployment: str, excel_context_understanding: str, verbose: bool = False):
        """
        Initialize the ValidationModule.

        Args:
            client: OpenAI client instance
            deployment: Model deployment name
            excel_context_understanding: Excel context for understanding
        """
        self.client = client
        self.deployment = deployment
        self.excel_context_understanding = excel_context_understanding
        self.verbose = verbose

    def reflect(self, execution_result: Dict[str, Any], user_question: str, understanding_output: str) -> Dict[str, Any]:
        """
        Reflect on and validate the execution results.

        Args:
            execution_result: Complete result from ExecutionModule
            user_question: Original user question
            understanding_output: Output from UnderstandingModule

        Returns:
            Dictionary containing validation results and feedback
        """
        logger.info("Starting validation on execution results")

        # Create validation prompt
        messages = self._create_validation_prompt(
            execution_result,
            user_question,
            understanding_output
        )

        # Get validation analysis
        try:
            validation_analysis = self._get_llm_response(messages)

            # Parse the validation response
            validation_result = self._parse_validation_response(validation_analysis)

            logger.info(f"Validation completed. Confidence: {validation_result['confidence_score']:.2f}")
            logger.info(f"Validation: {'PASSED' if validation_result['validation_passed'] else 'FAILED'}")

            if validation_result['validation_passed']:
                logger.info("Answer validated - ready for final output")
                validation_result['verified_answer'] = execution_result.get("answer", "")
                validation_result['requires_reexecution'] = False
            else:
                logger.warning("Issues found - recommending re-execution")
                validation_result['requires_reexecution'] = True

            return validation_result

        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            return {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [f"Validation process failed: {str(e)}"],
                "improvement_feedback": "Unable to provide feedback due to validation error. Please review the execution manually.",
                "final_assessment": "Unable to validate due to validation error",
                "verified_answer": "",
                "requires_reexecution": False  # Don't retry if validation itself failed
            }

    def _create_validation_prompt(self, execution_result: Dict[str, Any], user_question: str, understanding_output: str) -> list:
        """Create a comprehensive validation prompt for the LLM."""
        # Extract key information from execution result
        execution_success = execution_result.get("success", False)
        final_answer = execution_result.get("answer", "No answer provided")
        total_turns = execution_result.get("total_turns", 0)
        execution_summary = execution_result.get("execution_summary", {})
        conversation_history = execution_result.get("conversation_history", [])

        # Format full conversation history
        conversation_history_text = self._format_full_conversation_history(conversation_history)

        prompt_text = build_validation_prompt(
            user_question=user_question,
            excel_context_understanding=self.excel_context_understanding,
            execution_success=execution_success,
            total_turns=total_turns,
            final_answer=final_answer,
            execution_summary=execution_summary,
            conversation_history_text=conversation_history_text
        )

        return [{"role": "user", "content": prompt_text}]

    def _format_full_conversation_history(self, conversation_history: list) -> str:
        """Format the complete conversation history including thoughts, code, and outputs."""
        if not conversation_history:
            return "No conversation history available."

        formatted_parts = []
        turn_count = 0

        for i, msg in enumerate(conversation_history):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Skip the first system message and first user message (initial context)
            if i == 0 and role == "system":
                continue
            if i == 1 and role == "user":
                continue

            if role == "assistant":
                turn_count += 1
                formatted_parts.append(f"\n**TURN {turn_count} - AGENT RESPONSE:**")

                # Check if this contains code
                if "```python" in content:
                    # Split content into thoughts and code
                    parts = content.split("```python")
                    if len(parts) > 1:
                        # Thoughts before code
                        if parts[0].strip():
                            formatted_parts.append(f"**Thoughts:** {parts[0].strip()}")

                        # Extract and format code
                        code_part = parts[1].split("```")[0]
                        formatted_parts.append(f"**Code Executed:**")
                        formatted_parts.append(f"```python\n{code_part.strip()}\n```")

                        # Any thoughts after code
                        remaining = "```".join(parts[1].split("```")[1:])
                        if remaining.strip():
                            formatted_parts.append(f"**Additional Thoughts:** {remaining.strip()}")
                    else:
                        formatted_parts.append(f"**Content:** {content}")
                else:
                    # Check if this is a final answer
                    if "Final Answer:" in content:
                        formatted_parts.append(f"**Final Answer Provided:** {content}")
                    else:
                        formatted_parts.append(f"**Thoughts:** {content}")

            elif role == "user":
                # This is typically code execution results or feedback
                if "Code execution result:" in content:
                    formatted_parts.append(f"**Code Execution Result:**")
                    # Extract the actual result
                    result_content = content.replace("Code execution result:", "").strip()
                    formatted_parts.append(f"```\n{result_content}\n```")
                elif "Code execution error:" in content:
                    formatted_parts.append(f"**Code Execution Error:**")
                    error_content = content.replace("Code execution error:", "").strip()
                    formatted_parts.append(f"```\n{error_content}\n```")
                else:
                    formatted_parts.append(f"**User Feedback:** {content}")

        return "\n".join(formatted_parts)

    def _get_llm_response(self, messages: list, max_retries: int = 5) -> str:
        """Get response from the LLM with retry logic."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                )

                if self.verbose:
                    print("="*50)
                    print("VALIDATION MODULE LLM RESPONSE CONTENT:")
                    print("="*50)
                    print(response.choices[0].message.content)
                    print("="*50)

                return response.choices[0].message.content

            except Exception as e:
                last_exception = e
                logger.error(f"LLM Error (attempt {attempt + 1}/{max_retries}): {str(e)}")

                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise last_exception

    def _parse_validation_response(self, validation_text: str) -> Dict[str, Any]:
        """Parse the structured validation response from the LLM."""
        try:
            # Initialize default values
            result = {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [],
                "improvement_feedback": "",
                "final_assessment": "",
                "verified_answer": "",
                "requires_reexecution": False
            }

            # Parse validation status (handle both ** and no ** formats)
            validation_match = re.search(r'(\*\*)?VALIDATION_STATUS:(\*\*)?\s*\[?(PASSED|FAILED)\]?', validation_text, re.IGNORECASE)
            if validation_match:
                result["validation_passed"] = validation_match.group(3).upper() == "PASSED"

            # Parse confidence score (handle both ** and no ** formats)
            confidence_match = re.search(r'(\*\*)?CONFIDENCE_SCORE:(\*\*)?\s*\[?([0-9]*\.?[0-9]+)\]?', validation_text)
            if confidence_match:
                result["confidence_score"] = float(confidence_match.group(3))

            # Parse issues found (handle both ** and no ** formats)
            issues_section = re.search(r'(\*\*)?ISSUES_FOUND:(\*\*)?(.*?)(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?', validation_text, re.DOTALL)
            if issues_section:
                issues_text = issues_section.group(3).strip()
                issues = [line.strip('- ').strip() for line in issues_text.split('\n') if line.strip().startswith('-')]
                result["issues_found"] = [issue for issue in issues if issue and issue.lower() != "none identified"]

            # Parse improvement feedback (handle both ** and no ** formats)
            feedback_section = re.search(r'(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?(.*?)(\*\*)?FINAL_ASSESSMENT:(\*\*)?', validation_text, re.DOTALL)
            if feedback_section:
                result["improvement_feedback"] = feedback_section.group(3).strip()

            # Parse final assessment (handle both ** and no ** formats)
            assessment_section = re.search(r'(\*\*)?FINAL_ASSESSMENT:(\*\*)?(.*?)$', validation_text, re.DOTALL)
            if assessment_section:
                result["final_assessment"] = assessment_section.group(3).strip()

            return result

        except Exception as e:
            logger.error(f"Error parsing validation response: {str(e)}")
            return {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [f"Failed to parse validation response: {str(e)}"],
                "improvement_feedback": "Manual review required due to parsing error",
                "final_assessment": "Parsing error occurred during validation",
                "verified_answer": "",
                "requires_reexecution": False
            }