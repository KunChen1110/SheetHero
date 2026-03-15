import platform
import subprocess
import textwrap
from tkinter import messagebox
import re

import threading
from typing import List, Optional

import customtkinter as ctk
import os

from backend import Config
from backend import SheetHeroService

from frontend.components.colors import *
from frontend.components.file_display import FileDisplay
from frontend.components.footer_frame import FooterFrame
from frontend.components.chat_bubble import ChatBubble

# Opens a file specific to user's operating system
def open_file(path: str):
    if not path or not os.path.exists(path):
        messagebox.showerror("File Not Found", f"The file does not exist:\n{path}")
        return

    system = platform.system()
    # Windows open file
    if system == "Windows":
        os.startfile(path)

    # macOS open file
    elif system == "Darwin":
        subprocess.run(["open", path])

    # Linux / other open file
    else:
        try:
            subprocess.run(["xdg-open", path], check=True)
        except FileNotFoundError:
            subprocess.run(["less",path])


def _extract_saved_file_from_execution_results(result: dict) -> Optional[str]:
    """Get last saved xlsx path from execution step outputs."""
    try:
        all_exec = result.get("all_execution_results") or []
        for exec_result in reversed(all_exec):
            summary = (exec_result or {}).get("execution_summary") or {}
            steps = summary.get("execution_steps") or []
            for step in reversed(steps):
                result_text = str((step or {}).get("result") or "")
                for pattern in (r"Workbook saved to:\s*(.+?)(?:\n|$)", r"SAVED_FILE:\s*(.+?)(?:\n|$)"):
                    match = re.search(pattern, result_text)
                    if match:
                        candidate = match.group(1).strip()
                        if candidate and os.path.exists(candidate):
                            return candidate
    except Exception:
        return None
    return None


def _resolve_output_file_path(result: dict, configured_output_path: Optional[str]) -> Optional[str]:
    """Resolve the best output file path for the Open Excel Output button."""
    # 1) Prefer validated answer if it is an existing file
    answer = str(result.get("answer") or "").strip()
    if answer and os.path.exists(answer):
        return answer

    # 2) Use configured output path (file or directory)
    if configured_output_path:
        configured_output_path = os.path.expanduser(configured_output_path)
        if os.path.isfile(configured_output_path):
            return configured_output_path
        if os.path.isdir(configured_output_path):
            candidate = os.path.join(configured_output_path, "output.xlsx")
            if os.path.isfile(candidate):
                return candidate

    # 3) Parse execution logs for saved path
    return _extract_saved_file_from_execution_results(result)


# Page for prompting the model with selected files and config settings
class PromptPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._service: Optional[SheetHeroService] = None
        self._awaiting_clarification = False

        # Finish Button
        self.footer = None
        self.finish_button = None
        self.back_button = None
        self.create_footer()

        # Conversation Frame
        self.conversation_frame = None
        self.prompt_entry = None
        self.prompt_scroll = None
        self.create_conversation_frame()

        # Scroll Frame
        self.scroll_frame = None
        self.create_scroll_frame()

        self.chat_bubbles = []

        self.add_chat_bubble(f"Hello! Ask me anything.",False)

    # Updates the file list when menu is visible
    def on_show(self):
        self.update_file_list()


    # Creates the conversation frame
    def create_conversation_frame(self):
        # =-=-= Conversation Frame =-=-=
        self.conversation_frame = ctk.CTkFrame(
            master=self,
            fg_color=VERY_DARK_GREY,
        )
        self.conversation_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(30,5),
            pady=20,
        )

        self.prompt_scroll = ctk.CTkScrollableFrame(
            master=self.conversation_frame,
            orientation="vertical",
            fg_color=DARK_GREY,
            border_width=5,
            border_color=VERY_DARK_GREY,
        )
        self.prompt_scroll.pack(
            side="top",
            fill="both",
            expand=True,
        )

        self.prompt_entry = ctk.CTkTextbox(
            master=self.conversation_frame,
            height=80,
            wrap="word"
        )
        self.prompt_entry.pack(
            side="top",
            fill="x",
            padx=5,
            pady=5,
        )


    # Creates the scroll frame
    def create_scroll_frame(self):
        # =-=-= Scroll Frame =-=-=
        self.scroll_frame = ctk.CTkScrollableFrame(
            master=self,
            orientation="vertical",
            border_width=5,
            fg_color=DARK_GREY,
            border_color=VERY_DARK_GREY,
        )
        self.scroll_frame.pack(
            expand=True,
            fill="both",
            padx=(5,30),
            pady=20,
        )


    # Creates the footer
    def create_footer(self):
        # =-=-= Footer =-=-=
        self.footer = FooterFrame(master=self)

        # =-=-= Confirm Button =-=-=
        self.finish_button = ctk.CTkButton(
            master=self.footer,
            text="Confirm",
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            height=40,
            command=self.on_finish_pressed
        )
        self.finish_button.pack(
            side="right",
            padx=20,
        )

        # =-=-= Confirm Button =-=-=
        self.back_button = ctk.CTkButton(
            master=self.footer,
            text="Back",
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            height=40,
            command=self.on_back_pressed
        )
        self.back_button.pack(
            side="left",
            padx=20,
        )


    # Updates the file list
    def update_file_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for i in range(len(self.controller.selected_files)):
            file_name = os.path.basename(self.controller.selected_files[i])

            file_display = FileDisplay(
                self.scroll_frame,
                text=f"#{i+1} {file_name}",
                command=lambda index=i: self.remove_file(index)
            )
            file_display.pack(
                fill="x",
                pady=2,
                padx=2
            )


    # Removes a file from the selected files
    def remove_file(self,index):
        if index < len(self.controller.selected_files):
            self.controller.selected_files.pop(index)
            self.update_file_list()


    # Triggered when the back button is pressed
    def on_back_pressed(self):
        self._service = None
        self._awaiting_clarification = False
        self.controller.show_page("ConfigPage")


    # Triggered when the finish button is pressed
    def on_finish_pressed(self):
        prompt = self.prompt_entry.get("1.0", "end-1c").strip()

        if not prompt:
            messagebox.showwarning("Warning", "Please enter a prompt.")
            return

        if not self.controller.selected_files:
            messagebox.showwarning("Warning", "Please upload the files to query on")
            return

        self.start_query(prompt)


    # Updates all the chat bubbles in the conversation frame
    def update_chat_bubbles(self):
        for widget in self.prompt_scroll.winfo_children():
            widget.destroy()

        for bubble_data in self.chat_bubbles:
            bubble = ChatBubble(
                master=self.prompt_scroll,
                text=bubble_data["text"],
                color=bubble_data["color"]
            )
            bubble.pack(
                side="top",
                pady=5,
                padx=10,
                fill="x"
            )

            # If the bubble has buttons, add them into a frame
            if bubble_data.get("buttons"):
                button_frame = ctk.CTkFrame(
                    master=self.prompt_scroll,
                    fg_color=VERY_DARK_GREY,
                    corner_radius=0,
                    height=40
                )
                button_frame.pack(
                    side="top",
                    padx=10,
                    fill="x"
                )

                for label, command in bubble_data["buttons"]:
                    button = ctk.CTkButton(
                        master=button_frame,
                        text=label,
                        height=30,
                        fg_color=GREEN,
                        hover_color=HOVER_GREEN,
                        command=command
                    )
                    button.pack(
                        expand=True,
                        fill="x",
                        side="left",
                        pady=5,
                        padx=5,
                    )


    # Creates a conversation bubble to the conversation frame, different color if it's the users text
    def add_chat_bubble(self, text: str, is_user: bool, buttons: Optional[list] = None):
        color = VERY_DARK_GREY

        # If it's the user's text, use a different color
        if is_user:
            color = MID_GREY

        # Add the bubble to the list
        self.chat_bubbles.append({
            "text": text,
            "color": color,
            "buttons": buttons or []
        })

        # Update the bubble list
        self.update_chat_bubbles()


    # Starts the query, and sends the prompt to the model
    def start_query(self, prompt):
        self.add_chat_bubble(f"{prompt}",True)
        self.add_chat_bubble(f"Thinking...",False)
        self.prompt_entry.delete("1.0", "end")
        self.finish_button.configure(state="disabled")
        is_clarification_reply = self._awaiting_clarification and self._service is not None

        # Starts a threaded worker to allow the UI to be used during the agent running
        def worker():
            api_key: str = self.controller.api_key
            base_url: Optional[str] = self.controller.base_url
            deployment: str = self.controller.deployment
            max_turns: int = self.controller.max_turns
            selected_files: List[str] = self.controller.selected_files
            export_path: str = self.controller.export_path

            try:
                # Create the config
                config = Config()
                config.api_key = api_key
                config.base_url = base_url
                config.deployment = deployment
                config.max_turns = max_turns
                config.enable_diagnose = bool(self.controller.enable_diagnose)
                config.output_mode = "file"
                config.output_file = export_path

                if not is_clarification_reply or self._service is None:
                    self._service = SheetHeroService(config=config)
                    response = self._service.submit_turn(prompt, selected_files)
                else:
                    response = self._service.submit_clarification(prompt)

                response_type = str(response.get("type") or "")
                if response_type == "clarification":
                    self._awaiting_clarification = True
                    self.add_chat_bubble(str(response.get("message") or "Please clarify your answer."), False)
                    details_markdown = str(response.get("details_markdown") or "").strip()
                    if details_markdown:
                        self.add_chat_bubble(details_markdown, False)
                elif response_type == "final":
                    self._awaiting_clarification = False
                    result = response.get("result") if isinstance(response.get("result"), dict) else {}
                    if not isinstance(result, dict):
                        result = {}

                    if {"success", "confidence_score", "total_iterations", "total_duration"} <= set(result.keys()):
                        result_text = textwrap.dedent(
                        f"""
                        Success:{'✅' if result['success'] else '❌'}
                        Confidence: {result['confidence_score']:.2f}/1.0
                        Iterations: {result['total_iterations']}
                        Duration: {result['total_duration']:.2f}s
                        """)

                        if result.get('issues_found'):
                            result_text += "\nIssues Found:\n" + "\n".join([f" - {i}" for i in result['issues_found']])

                        if result.get('improvement_feedback'):
                            result_text += f"\n\nImprovement Feedback:\n{result['improvement_feedback']}"

                        short_answer = str(result.get("short_answer") or response.get("message") or "").strip()
                        if short_answer:
                            result_text += f"\n\nSummary:\n{short_answer}"

                        buttons = []
                        if result.get("verbose_log_path"):
                            buttons.append((
                                "Open Markdown Log",
                                lambda path=result["verbose_log_path"]: open_file(path)
                            ))

                        output_file_path = _resolve_output_file_path(result, config.output_file)
                        if output_file_path and os.path.exists(output_file_path):
                            buttons.append((
                                "Open Excel Output",
                                lambda path=output_file_path: open_file(path)
                            ))

                        self.add_chat_bubble(f"{result_text}", False, buttons=buttons)
                    else:
                        message = str(response.get("message") or result.get("final_answer") or "Completed.")
                        self.add_chat_bubble(message, False)
                    self._service = None
                else:
                    self._awaiting_clarification = False
                    self._service = None
                    self.add_chat_bubble(str(response.get("message") or "Unknown error."), False)

            # Send error if fails
            except Exception as error:
                self._awaiting_clarification = False
                self._service = None
                self.add_chat_bubble(f"Error: {error}",False)

            self.finish_button.configure(state="enabled")

        # Start the worker on another thread
        threading.Thread(target=worker, daemon=True).start()
