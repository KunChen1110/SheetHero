"""Base runtime helpers for stages."""


class StageRuntime:
    """Shared logging helpers for stage runtimes."""

    def __init__(self, progress_log_file=None):
        self.progress_log_file = progress_log_file

    def _log_to_file(self, message: str):
        if self.progress_log_file:
            self.progress_log_file.write(message + "\n")
            self.progress_log_file.flush()
