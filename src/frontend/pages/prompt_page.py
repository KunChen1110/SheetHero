import platform
import subprocess
import textwrap
from tkinter import messagebox

import threading
from typing import List, Optional

import customtkinter as ctk
import os

from backend.config import Config
from backend.core import SheetHero

from frontend.components.colors import *
from frontend.components.file_display import FileDisplay
from frontend.components.footer_frame import FooterFrame
from frontend.components.chat_bubble import ChatBubble

# Opens a file specific to user's operating system
def open_file(path: str):
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


# Page for prompting the model with selected files and config settings
class PromptPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

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

        self.chat_bubbles.append({
            "text": text,
            "color": color,
            "buttons": buttons or []
        })
        self.update_chat_bubbles()


    # Starts the query, and sends the prompt to the model
    def start_query(self, prompt):
        self.add_chat_bubble(f"{prompt}",True)
        self.add_chat_bubble(f"Thinking...",False)
        self.prompt_entry.delete("1.0", "end")
        self.finish_button.configure(state="disabled")

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
                config.output_mode = "file"
                config.output_file = export_path

                # Create and run the agent
                agent = SheetHero(
                    excel_paths=selected_files,
                    config=config
                )
                result = agent.run(
                    user_question=prompt
                )

                # Get the result from the agent
                result_text = textwrap.dedent(
                f"""
                Success:{'✅' if result['success'] else '❌'}
                Confidence: {result['confidence_score']:.2f}/1.0
                Iterations: {result['total_iterations']}
                Duration: {result['total_duration']:.2f}s
                """)

                # Send if there are issues
                if result['issues_found']:
                    result_text += "\nIssues Found:\n" + "\n".join([f" - {i}" for i in result['issues_found']])

                # Send if there is feedback
                if result.get('improvement_feedback'):
                    result_text += f"\n\nImprovement Feedback:\n{result['improvement_feedback']}"

                # If it succeeds, create buttons to link the markdown and excel
                if result['success']:
                    buttons = []

                    if result.get("verbose_log_path"):
                        buttons.append((
                            "Open Markdown Log",
                            lambda path=result["verbose_log_path"]: open_file(path)
                        ))

                    if config.output_file and os.path.exists(config.output_file):
                        buttons.append((
                            "Open Excel Output",
                            lambda path=config.output_file: open_file(path)
                        ))

                    self.add_chat_bubble(f"{result_text}", False, buttons=buttons)
                else:
                    self.add_chat_bubble(f"{result_text}", False)

            # Send error if fails
            except Exception as error:
                self.add_chat_bubble(f"Error: {error}",False)

            self.finish_button.configure(state="enabled")

        # Start the worker on another thread
        threading.Thread(target=worker, daemon=True).start()

