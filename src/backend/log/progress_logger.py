"""Progress logging with markdown formatting for SheetHero."""

from datetime import datetime
from pathlib import Path
from typing import Optional


class ProgressLogger:
    """Write progress updates to a session-scoped markdown log."""

    def __init__(self, excel_paths, base_dir: Optional[Path] = None):
        if base_dir is None:
            log_dir = Path("/home/scygl3/GRP/team29_project/artifects/logger")
        else:
            log_dir = Path(base_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if excel_paths:
            first_file = Path(excel_paths[0]).stem
            session_id = f"sheethero_{first_file}"
        else:
            session_id = "sheethero"

        self._path = log_dir / f"{session_id}_{timestamp}.md"
        self._file = open(self._path, 'w', encoding='utf-8')
        self._file.write("# SheetHero Verbose Log\n\n")
        self._file.write(
            f"**Session started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        self._file.write("---\n\n")
        self._file.flush()

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def file(self):
        return self._file

    def log(self, message: str, to_terminal: bool = False):
        formatted = self._format_progress_message(message)
        self.log_raw(formatted)

        # Optional terminal output if needed in future
        if to_terminal:
            print(message)

    def log_raw(self, message: str):
        if self._file:
            self._file.write(message + "\n")
            self._file.flush()

    def log_stage(self, stage: str):
        self.log(f"### {stage}")

    def close(self) -> Optional[str]:
        if self._file:
            self._file.write("\n---\n\n")
            self._file.write(
                f"**Session ended:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            self._file.close()
            self._file = None
            return self.path
        return None

    def _format_progress_message(self, message: str) -> str:
        cleaned = message.strip()

        if cleaned.startswith("=" * 40) or cleaned.startswith("=" * 60) or cleaned.startswith("=" * 80):
            return "\n---\n"

        if cleaned.startswith("-" * 40) or cleaned.startswith("-" * 60):
            return "\n**" + cleaned.replace("-", "").strip() + "**\n"

        if "[FINAL SUMMARY]" in cleaned:
            return f"\n## {cleaned}\n"
        if "[STAGE" in cleaned or "[ITERATION" in cleaned:
            return f"\n### {cleaned}\n"
        if any(prefix in cleaned for prefix in [
            "[SheetHero]",
            "[SUCCESS",
            "[STOPPING",
            "[CONTINUE",
            "[MAX ITERATIONS",
            "[Excel]",
        ]):
            return f"**{cleaned}**"

        if cleaned.startswith("❌") or cleaned.startswith("⚠️"):
            return f"⚠️ {cleaned.lstrip('❌⚠️').strip()}"
        if cleaned.startswith("✅"):
            return f"✅ {cleaned.lstrip('✅').strip()}"

        return cleaned
