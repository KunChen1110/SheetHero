import json
from dataclasses import dataclass, field

from .config.settings import Config
from .service.sheethero_service import SheetHeroService


@dataclass
class InputBuffer:
    excel_paths: list[str] = field(default_factory=list)
    prompt: str | None = None

    def clear(self) -> None:
        self.excel_paths.clear()
        self.prompt = None

    def ready(self) -> bool:
        return self.prompt is not None


def _handle_path(buffer: InputBuffer, line: str) -> None:
    payload = line[len("!path="):].strip()
    if not payload:
        buffer.excel_paths = []
        print("[paths set] []")
        return
    try:
        buffer.excel_paths = json.loads(payload)
        print(f"[paths set] {buffer.excel_paths}")
    except json.JSONDecodeError:
        print("Error: !path expects a JSON list, e.g. !path=[\"a.xlsx\"]")


def main() -> None:
    service = SheetHeroService(config=Config())
    buffer = InputBuffer()
    awaiting_clarification = False

    print("SheetHero CLI (debug mode)")
    print("Type `exit` to quit.")
    print("Type `run` to execute the current turn.")

    while True:
        line = input(">>> ").strip()

        if line == "exit":
            break

        if line == "reset":
            buffer.clear()
            awaiting_clarification = False
            print("[buffer cleared]")
            continue

        if line.startswith("!path="):
            _handle_path(buffer, line)
            continue

        if line == "run":
            if not buffer.ready():
                print("Error: prompt not set.")
                continue

            result = service.submit_turn(
                prompt=buffer.prompt or "",
                excel_paths=buffer.excel_paths,
                user_input_callback=lambda msg: input(f"Agent: {msg}\nYou: "),
            )

            print(f"Agent: {result.get('message')}")
            if result.get("type") == "clarification":
                awaiting_clarification = True
            else:
                buffer.clear()
                awaiting_clarification = False
            continue

        if awaiting_clarification:
            result = service.submit_turn(
                prompt=line,
                excel_paths=buffer.excel_paths,
                user_input_callback=lambda msg: input(f"Agent: {msg}\nYou: "),
            )
            print(f"Agent: {result.get('message')}")
            if result.get("type") == "clarification":
                awaiting_clarification = True
            else:
                buffer.clear()
                awaiting_clarification = False
            continue

        # Treat any other input as a prompt only; run on explicit `run`.
        buffer.prompt = line
        print(f"[prompt set] {buffer.prompt}")


if __name__ == "__main__":
    main()
