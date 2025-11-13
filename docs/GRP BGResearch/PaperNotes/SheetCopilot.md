## SheetCopilot: Bringing Software Productivity to the Next Level through Large Language Models [link](https://arxiv.org/abs/2305.19308?utm_source=chatgpt.com) [project](https://sheetcopilot.github.io)


This research introduces a **state-driven spreadsheet automation framework** named **SheetCopilot**, which enables Large Language Models (LLMs) to perform spreadsheet operations through **iterative planning, feedback, and correction**.
The system allows the LLM to act as a “co-pilot,” decomposing complex tasks into structured, executable spreadsheet actions while maintaining accuracy through continuous self-revision.




### Workflow:
1.  The **Planning Module** interprets the user’s natural-language request and decomposes it into **atomic spreadsheet actions** (e.g., Filter, Write, Merge).
2.  The **State Controller** executes one action at a time within a **closed-loop framework**, updating the spreadsheet state after each operation.
3.  The **Revision Module** monitors for **errors or inconsistencies**, providing feedback and documentation for the LLM to self-correct.
4.  The process iterates—**plan → execute → revise → replan**—until the task is fully completed with validated results.


### Planning Module：
The LLM interprets the user’s natural-language instruction and the spreadsheet structure.
It decomposes the task into atomic actions — simple, predefined operations such as Filter(), Write(), or CreateChart().
These actions form a structured plan that the system can execute step by step.


### State Controller：
Instead of generating the entire solution at once, the model performs one operation at a time within a state-machine framework.
After each action, the system updates the spreadsheet state and provides feedback to the LLM, ensuring stability and reducing cascading errors.


### Revision Module：
If an operation fails (e.g., wrong parameters or invalid action), the system automatically returns the error message and the corresponding documentation to the LLM.
The model then revises its previous step and re-executes until success, forming a self-correcting cycle.


### Evaluation:
1.  The “atomic action” idea can be adapted to our data-cleaning function library, where each cleaning step (e.g., TrimWhitespace, FillMissing, StandardizeCase) is a safe and interpretable operation.
2.  The state-machine execution loop fits perfectly with our goal of iterative cleaning and verification — detect → clean → validate → retry if needed.
3.  The revision mechanism suggests how we can integrate automatic error handling when cleaning fails (e.g., switching from filling to dropping missing values).

