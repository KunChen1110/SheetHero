from .agent import SheetHero
from .config.settings import Config
"""
Here is the usage of the SheetHero API

-----------------------
Single-turn execution
-----------------------

    config = Config(
        api_key="YOUR_KEY",
        output_mode="file",
    )

    agent = SheetHero(
        excel_paths=["data.xlsx"],
        config=config,
    )

    result = agent.run(
        user_question="Summarise sales by region and save to a new sheet."
    )

-----------------------
Multi-turn interactive session (QA loop)
-----------------------

    agent = SheetHero(excel_paths=["data.xlsx"], config=config)

    session = agent.start_session(
        "Generate meeting schedules for each tutor."
    )

    response = agent.step(session)

    while response["type"] in ("clarification", "progress"):
        if response["type"] == "clarification":
            print("Agent:", response["message"])
            user_reply = input("You: ")
            response = agent.step(session, user_reply)
        else:
            # progress: let agent continue autonomously
            response = agent.step(session)

    print("Final answer:", response["result"]["final_answer"])

-----------------------
Main public APIs
-----------------------

- SheetHero.run(user_question: str) -> Dict
    Run the agent in single-turn mode.

- SheetHero.start_session(user_question: str) -> SheetHeroSession
    Create a new interactive session.

- SheetHero.step(session, user_input=None) -> AgentResponse
    Perform one interaction step in an ongoing session.
    Validation may finalize without re-execution when it returns
    requires_reexecution=False.

"""


__all__ = ["SheetHero", "Config"]
