"""Parse validation LLM responses into structured results."""

import json
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

            text = validation_text or ""

            # 1) Prefer strict JSON if model returns object output.
            json_obj = self._try_parse_json_object(text)
            if isinstance(json_obj, dict):
                self._merge_from_json(result, json_obj)

            # 2) Legacy label format: VALIDATION_STATUS / CONFIDENCE_SCORE / ...
            validation_match = re.search(
                r'(\*\*)?VALIDATION_STATUS:(\*\*)?\s*\[?(PASSED|FAILED)\]?',
                text,
                re.IGNORECASE
            )
            if validation_match:
                result["validation_passed"] = (
                    validation_match.group(3).upper() == "PASSED"
                )

            confidence_match = re.search(
                r'(\*\*)?CONFIDENCE_SCORE:(\*\*)?\s*\[?([0-9]*\.?[0-9]+)\]?',
                text
            )
            if confidence_match:
                result["confidence_score"] = float(confidence_match.group(3))

            # 3) Offline format fallback: validation_passed / confidence_score / ...
            bool_match = re.search(r"validation_passed\s*[:=]\s*(true|false)", text, re.IGNORECASE)
            if bool_match:
                result["validation_passed"] = bool_match.group(1).lower() == "true"
            cs_match = re.search(r"confidence_score\s*[:=]\s*([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
            if cs_match:
                result["confidence_score"] = float(cs_match.group(1))

            issues_section = re.search(
                r'(\*\*)?ISSUES_FOUND:(\*\*)?(.*?)(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?',
                text,
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
            elif not result["issues_found"]:
                issues_key_section = re.search(
                    r"issues_found\s*[:=]\s*(.*?)(?:improvement_feedback|final_assessment|$)",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if issues_key_section:
                    issues_text = issues_key_section.group(1).strip()
                    parsed_issues = []
                    # bullet-style
                    for line in issues_text.splitlines():
                        line = line.strip()
                        if line.startswith("- "):
                            parsed_issues.append(line[2:].strip())
                    if not parsed_issues and issues_text and issues_text.lower() not in {"[]", "none", "none identified.", "none identified"}:
                        parsed_issues = [issues_text]
                    result["issues_found"] = [i for i in parsed_issues if i]

            feedback_section = re.search(
                r'(\*\*)?IMPROVEMENT_FEEDBACK:(\*\*)?(.*?)(\*\*)?FINAL_ASSESSMENT:(\*\*)?',
                text,
                re.DOTALL
            )
            if feedback_section:
                result["improvement_feedback"] = feedback_section.group(3).strip()
            elif not result["improvement_feedback"]:
                fb_match = re.search(
                    r"improvement_feedback\s*[:=]\s*(.*?)(?:final_assessment|$)",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if fb_match:
                    result["improvement_feedback"] = fb_match.group(1).strip()

            assessment_section = re.search(
                r'(\*\*)?FINAL_ASSESSMENT:(\*\*)?(.*?)$',
                text,
                re.DOTALL
            )
            if assessment_section:
                result["final_assessment"] = assessment_section.group(3).strip()
            elif not result["final_assessment"]:
                ass_match = re.search(
                    r"final_assessment\s*[:=]\s*(.*?)$",
                    text,
                    re.IGNORECASE | re.DOTALL
                )
                if ass_match:
                    result["final_assessment"] = ass_match.group(1).strip()

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

    @staticmethod
    def _try_parse_json_object(text: str) -> Dict[str, Any] | None:
        if not text:
            return None
        candidates = []
        fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            candidates.append(fenced.group(1))
        plain = re.search(r"(\{.*\})", text, re.DOTALL)
        if plain:
            candidates.append(plain.group(1))
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        return None

    @staticmethod
    def _merge_from_json(result: Dict[str, Any], obj: Dict[str, Any]) -> None:
        if "validation_passed" in obj:
            result["validation_passed"] = bool(obj.get("validation_passed"))
        if "confidence_score" in obj:
            try:
                result["confidence_score"] = float(obj.get("confidence_score"))
            except Exception:
                pass
        if "issues_found" in obj:
            raw = obj.get("issues_found")
            if isinstance(raw, list):
                result["issues_found"] = [str(i).strip() for i in raw if str(i).strip()]
            elif isinstance(raw, str) and raw.strip():
                if raw.strip().lower() not in {"none", "none identified", "none identified."}:
                    result["issues_found"] = [raw.strip()]
        if "improvement_feedback" in obj:
            feedback = obj.get("improvement_feedback")
            if isinstance(feedback, list):
                result["improvement_feedback"] = "\n".join(str(i) for i in feedback if str(i).strip())
            elif feedback is not None:
                result["improvement_feedback"] = str(feedback).strip()
        if "final_assessment" in obj and obj.get("final_assessment") is not None:
            result["final_assessment"] = str(obj.get("final_assessment")).strip()
