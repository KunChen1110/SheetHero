"""Execution module for multi-turn reasoning and code execution."""

import io
import re
import sys
import time
import random
import traceback
from typing import Dict, Any, Optional, Tuple

from openai import RateLimitError

from utils.logger import setup_logger
from modules.prompts import EXECUTION_SYSTEM_INTRO, EXECUTION_HELPER_SECTIONS, build_execution_user_prompt

logger = setup_logger(__name__)


class ExecutionModule:
    """
    Module responsible for multi-turn reasoning and code execution based on understanding context.
    Handles its own conversation flow internally and returns the final result.
    """

    def __init__(self, client, deployment: str, code_globals: dict, code_locals: dict,
                 excel_context_execution: str, output_instruction: Optional[str] = None,
                 progress_log_file=None):
        """
        Initialize the ExecutionModule.

        Args:
            client: OpenAI client instance
            deployment: Model deployment name
            code_globals: Global variables for code execution
            code_locals: Local variables for code execution
            excel_context_execution: Excel context for execution
            output_instruction: Additional guidance on how to deliver results
            progress_log_file: File handle for progress logging (optional)
        """
        self.client = client
        self.deployment = deployment
        self.code_globals = code_globals
        self.code_locals = code_locals
        self.excel_context_execution = excel_context_execution
        self.output_instruction = output_instruction or ""
        self.progress_log_file = progress_log_file
        self.conversation_history = []
    
    def _log_to_file(self, message: str):
        """Write message to progress log file if available."""
        if self.progress_log_file:
            self.progress_log_file.write(message + "\n")
            self.progress_log_file.flush()

    def _get_system_prompt(self) -> dict:
        """Create the system prompt for the conversation."""
        system_parts = [EXECUTION_SYSTEM_INTRO]
        if self.output_instruction:
            system_parts.append(f"\n**OUTPUT REQUIREMENTS:**\n{self.output_instruction}\n")
        system_parts.append(EXECUTION_HELPER_SECTIONS)

        system_content = "".join(system_parts)
        return {"role": "system", "content": system_content}

    def _create_initial_user_prompt(self, understanding_output: str, user_question: str) -> dict:
        """Create the initial user prompt for the conversation."""
        user_content = build_execution_user_prompt(
            self.excel_context_execution,
            understanding_output,
            user_question
        )
        return {"role": "user", "content": user_content}

    def run(self, understanding_output: str, user_question: str, max_turns: int = 20) -> Dict[str, Any]:
        """
        Run the execution module with understanding context and user question.

        Args:
            understanding_output: Output from UnderstandingModule
            user_question: Original user question
            max_turns: Maximum number of conversation turns

        Returns:
            Dictionary containing execution results and conversation history
        """
        logger.info(f"Starting multi-turn analysis for: '{user_question}'")

        # Initialize conversation with system prompt and initial user prompt
        self.conversation_history = [self._get_system_prompt()]
        initial_prompt = self._create_initial_user_prompt(understanding_output, user_question)
        self.conversation_history.append(initial_prompt)

        execution_steps = []  # Track key execution steps

        for turn in range(max_turns):
            logger.info(f"Execution turn {turn + 1}")
            
            # Log turn number to file
            self._log_to_file(f"\n---\n\n### Execution Turn {turn + 1}\n")

            try:
                response_message = self._get_llm_response()
                self.conversation_history.append(response_message)

                # Parse response for code action or final answer
                thought, code_action = self._parse_llm_response(response_message.content)
                
                # Log thought process to file
                if thought:
                    self._log_to_file(f"\n**Thought (Turn {turn + 1}):**\n{thought}\n")

                if code_action is None:
                    # No code to execute, check if it's a final answer
                    if thought and "Final Answer:" in thought:
                        # Extract the final answer from the content
                        final_answer_match = re.search(r"Final Answer:\s*(.*?)$", thought, re.DOTALL)
                        if final_answer_match:
                            final_answer = final_answer_match.group(1).strip()
                        else:
                            final_answer = thought.replace("Final Answer:", "").strip()

                        logger.info(f"Final answer found: {final_answer}")
                        
                        # Log final answer to file
                        self._log_to_file(f"\n**Final Answer (Turn {turn + 1}):**\n{final_answer}\n")

                        return {
                            "success": True,
                            "answer": final_answer,
                            "total_turns": turn + 1,
                            "conversation_history": self._format_conversation_history(),
                            "execution_summary": self._generate_execution_summary(execution_steps, final_answer)
                        }
                    else:
                        # No valid action found, ask for clarification
                        logger.warning("No valid action found, asking for clarification")
                        reminder = (
                            "CRITICAL FORMAT VIOLATION: You must respond in EXACTLY one of these formats:\n\n"
                            "FORMAT A - Thinking + Code:\n"
                            "**Thought:** [Your reasoning here]\n\n"
                            "```python\n# Your code here\n```\n\n"
                            "FORMAT B - Thinking + Final Answer:\n"
                            "**Thought:** [Your reasoning here]\n\n"
                            "Final Answer: Your answer here\n\n"
                            "NO other text is allowed. Start with **Thought:** ALWAYS."
                        )
                        self.conversation_history.append({"role": "user", "content": reminder})
                        continue

                # Execute code action
                logger.info(f"Executing Python code:\n{code_action}")
                
                # Log code to file
                self._log_to_file(f"\n**Executing Python code (Turn {turn + 1}):**\n```python\n{code_action}\n```\n")

                try:
                    execution_result = self._execute_code(code_action)
                    observation = f"Code execution result:\n{execution_result}"
                    logger.info(f"Execution result:\n{execution_result}")
                    
                    # Log execution result to file
                    self._log_to_file(f"\n**Execution result (Turn {turn + 1}):**\n```\n{execution_result}\n```\n")

                    # Track this execution step
                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": execution_result,
                        "success": True
                    })

                    self.conversation_history.append({"role": "user", "content": observation})

                except Exception as e:
                    error_message = f"Code execution error: {str(e)}"
                    logger.error(f"Execution error: {error_message}")
                    
                    # Log error to file
                    self._log_to_file(f"\n**Execution error (Turn {turn + 1}):**\n```\n{error_message}\n```\n")

                    # Track this failed execution step
                    execution_steps.append({
                        "turn": turn + 1,
                        "code": code_action,
                        "result": error_message,
                        "success": False
                    })

                    self.conversation_history.append({"role": "user", "content": error_message})

            except Exception as e:
                logger.error(f"LLM Error: {str(e)}")
                return {
                    "success": False,
                    "answer": f"LLM communication error: {str(e)}",
                    "total_turns": turn + 1,
                    "conversation_history": self._format_conversation_history(),
                    "execution_summary": self._generate_execution_summary(execution_steps, None)
                }

        # Reached maximum turns without final answer
        logger.warning("Reached maximum turns without finding final answer")
        return {
            "success": False,
            "answer": "Unable to find a complete answer within the maximum number of turns.",
            "total_turns": max_turns,
            "conversation_history": self._format_conversation_history(),
            "execution_summary": self._generate_execution_summary(execution_steps, None)
        }

    def _execute_code(self, code: str) -> str:
        """Execute Python code in the Excel environment."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result = ""

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Merge locals into globals for better variable access in nested scopes
            combined_namespace = {**self.code_globals, **self.code_locals}

            # Execute the code with combined namespace
            exec(code, combined_namespace)

            # Update both globals and locals with any new variables
            self.code_globals.update({k: v for k, v in combined_namespace.items()
                                    if k not in self.code_globals or k in self.code_locals})
            self.code_locals.update(combined_namespace)

            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()

            if stdout_output:
                result += f"Output:\n{stdout_output}\n"

            if stderr_output:
                result += f"Errors/Warnings:\n{stderr_output}\n"

            # Check for result variable
            if 'result' in combined_namespace:
                result += f"Result variable: {combined_namespace['result']}\n"

            # Try to evaluate last expression if no output
            if not result.strip():
                lines = code.strip().split('\n')
                if lines:
                    last_line = lines[-1].strip()
                    if last_line and not any(last_line.startswith(kw) for kw in
                                           ['import ', 'from ', 'def ', 'class ', 'if ', 'for ', 'while ', 'try ', 'with ', 'print(']):
                        try:
                            last_result = eval(last_line, combined_namespace)
                            if last_result is not None:
                                result = f"Expression result: {last_result}"
                        except:
                            pass

            if not result.strip():
                result = "Code executed successfully (no output)"

        except Exception as e:
            result = f"Execution error: {str(e)}\nTraceback:\n{traceback.format_exc()}"

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        if len(result) <= 10000:
            return result
        else:
            return result[:10000] + "\n⚠️ **[OUTPUT TRUNCATED]** ⚠️\n"

    def _get_llm_response(self, max_retries: int = 5, base_delay: float = 1.0):
        """Get response from OpenAI with retry logic."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=self.conversation_history,
                )

                # Extract message
                choice = response.choices[0]
                message = choice.message

                # Verbose output removed - only logged to file
                return message

            except RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit, attempt {attempt + 1}/{max_retries}: {str(e)}")

                # Extract wait time from error message if available
                wait_time = self._extract_wait_time_from_error(str(e))

                if attempt < max_retries - 1:
                    if wait_time:
                        delay = wait_time + random.uniform(1, 3)
                        logger.info(f"Waiting {delay:.1f} seconds as suggested by API")
                    else:
                        delay = 10
                        logger.info(f"Waiting {delay:.1f} seconds (exponential backoff)")

                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed due to rate limiting")
                    break

            except Exception as e:
                last_exception = e
                logger.error(f"API error, attempt {attempt + 1}/{max_retries}: {str(e)}")

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Waiting {delay:.1f} seconds before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed")
                    break

        if last_exception:
            raise last_exception

    def _parse_llm_response(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse LLM response for Final Answer or Code Action"""

        # Check for Final Answer (with or without Thought prefix)
        if "Final Answer:" in content:
            return content.strip(), None

        # Check for Code Action
        code_match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            return None, code

        # No valid format found
        return content.strip(), None

    def _extract_wait_time_from_error(self, error_message: str) -> Optional[int]:
        """Extract wait time from rate limit error message."""
        try:
            # Look for patterns like "Try again in X seconds"
            match = re.search(r'try again in (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            # Look for other patterns like "Retry after X seconds"
            match = re.search(r'retry after (\d+) seconds?', error_message.lower())
            if match:
                return int(match.group(1))

            return None
        except:
            return None

    def _format_conversation_history(self) -> list:
        """Format conversation history for output."""
        formatted_history = []
        for msg in self.conversation_history:
            if hasattr(msg, 'dict'):
                formatted_history.append(msg.dict())
            elif isinstance(msg, dict):
                formatted_history.append(msg)
            else:
                # Convert other message types to dict format
                formatted_history.append({
                    "role": getattr(msg, 'role', 'unknown'),
                    "content": getattr(msg, 'content', str(msg))
                })
        return formatted_history

    def _generate_execution_summary(self, execution_steps: list, final_answer: Optional[str]) -> dict:
        """Generate a summary of the execution process."""
        successful_steps = [step for step in execution_steps if step["success"]]
        failed_steps = [step for step in execution_steps if not step["success"]]

        summary = {
            "total_code_executions": len(execution_steps),
            "successful_executions": len(successful_steps),
            "failed_executions": len(failed_steps),
            "execution_steps": execution_steps,
            "has_final_answer": final_answer is not None,
            "final_answer": final_answer
        }

        if execution_steps:
            summary["first_execution_turn"] = execution_steps[0]["turn"]
            summary["last_execution_turn"] = execution_steps[-1]["turn"]

        return summary