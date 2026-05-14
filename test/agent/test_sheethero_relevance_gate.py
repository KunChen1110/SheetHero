import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.agent.core.SheetHero import SheetHero
from backend.agent.core.session import SheetHeroSession


class _RejectingInteract:
    def workbook_matches_request(self, user_message: str, spreadsheet_summary: str) -> bool:
        assert "tutor" in user_message.lower()
        assert "Daily Spending" in spreadsheet_summary
        return False


class _UnexpectedUnderstanding:
    def run(self, *_args, **_kwargs):
        raise AssertionError("understanding should not run for mismatched workbook/task")


def test_understanding_blocks_when_uploaded_workbooks_do_not_match_task():
    hero = SheetHero.__new__(SheetHero)
    hero.interact_module = _RejectingInteract()
    hero.understanding_module = _UnexpectedUnderstanding()

    session = SheetHeroSession(
        original_query="Produce a tutor meeting schedule for students.",
        state="understanding",
    )
    session.current_workbooks = {"tc01_input01.xlsx": object()}
    session.spreadsheet_summary = "Files contain columns: Date, Category, Daily Spending (£), Notes."

    response = hero._handle_understanding(
        session,
        "Produce a tutor meeting schedule for students.",
    )

    assert response["type"] == "error"
    assert "uploaded spreadsheet files do not appear to match" in response["message"].lower()
    assert session.state == "done"
