"""Parse validation LLM responses into structured results."""

import re
from typing import Any, Dict

from ...log.logger_registry import LoggerRegistry
from ..base.response_parser import BaseResponseParser

logger = LoggerRegistry.setup_logger(__name__)


class ValidationResponseParser(BaseResponseParser):
    """Extract structured validation data from LLM response text."""

    def parse(self, validation_text: str) -> Dict[str, Any]:
        try:
            result = {
                "validation_passed": False,
                "confidence_score": 0.0,
                "issues_found": [],
                "improvement_feedback": "",
                "final_assessment": "",
                "verified_answer": "",
                "requires_reexecution": False
            }

            validation_match = re.search(
                r'(\*\*)?VALIDATION_STATUS:(\*\*)?\s*\[?(PASSED|FAILED)\]?',
                validation_text,
                re.IGNORECASE
            )
            if validation_match:
                result["validation_passed"] = (
                    validation_match.group(3).upper() == "PASSED"
                )

            confidence_match = re.search(
                r'(\*\*)?CONFIDENCE_SCORE:(\*\*)?\s*\[?([0-9]*\.?[0-9]+)\]?',
                validation_text
            )
            if confidence_match:
                result["confidence_score"] = float(confidence_match.group(3))

            issues_section = re.search(
                r'(\*\*)?ISSUES_FOUND:(\*\*)?(.*?)(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?',
                validation_text,
                re.DOTALL
            )
            if issues_section:
                issues_text = issues_section.group(3).strip()
                issues = [
                    line.strip('- ').strip()
                    for line in issues_text.split('\n')
                    if line.strip().startswith('-')
                ]
                result["issues_found"] = [
                    issue for issue in issues
                    if issue and issue.lower() != "none identified"
                ]

            feedback_section = re.search(
                r'(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?(.*?)(\*\*)?FINAL_ASSESSMENT:(\*\*)?',
                validation_text,
                re.DOTALL
            )
            if feedback_section:
                result["improvement_feedback"] = feedback_section.group(3).strip()

            assessment_section = re.search(
                r'(\*\*)?FINAL_ASSESSMENT:(\*\*)?(.*?)$',
                validation_text,
                re.DOTALL
            )
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
