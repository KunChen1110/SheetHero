from backend.stages.validation.core.parser import ValidationResponseParser


def test_parse_json_validation_payload():
    parser = ValidationResponseParser()
    payload = """```json
{
  "validation_passed": true,
  "confidence_score": 1,
  "issues_found": [],
  "improvement_feedback": [],
  "final_assessment": "All required features were correctly implemented."
}
```"""

    result = parser.parse(payload)

    assert result["validation_passed"] is True
    assert result["confidence_score"] == 1.0
    assert result["issues_found"] == []
    assert result["improvement_feedback"] == ""
    assert result["final_assessment"] == "All required features were correctly implemented."
