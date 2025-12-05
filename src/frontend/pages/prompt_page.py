from tkinter import messagebox

import customtkinter as ctk
import os

from backend.config import Config
from backend.core import SheetHero
from frontend.components.colors import *
from frontend.components.file_display import FileDisplay
from frontend.components.footer_frame import FooterFrame

class PromptPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Finish Button
        self.footer = None
        self.finish_button = None
        self.back_button = None
        self.create_footer()

        # Data Frame
        self.data_display_frame = None
        self.feedback_label = None
        self.prompt_entry = None
        self.create_data_display_frame()

        # Scroll Frame
        self.scroll_frame = None
        self.create_scroll_frame()

    # Updates the file list when menu is visible
    def on_show(self):
        self.update_file_list()


    # Creates the data display frame
    def create_data_display_frame(self):
        # =-=-= Data Display Frame =-=-=
        self.data_display_frame = ctk.CTkFrame(
            master=self,
            fg_color=VERY_DARK_GREY,
            width=300,
        )
        self.data_display_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(30,5),
            pady=20,
        )

        # =-=-= Prompt Entry =-=-=
        self.prompt_entry = ctk.CTkTextbox(
            master=self.data_display_frame,
            height=100,
            wrap="word",
        )
        self.prompt_entry.pack(
            side="top",
            fill="both",
            padx=5,
            pady=(5,10),
        )

        # =-=-= Feedback Label =-=-=
        self.feedback_label = ctk.CTkLabel(
            master=self.data_display_frame,
            fg_color=DARK_GREY,
            text="Feedback",
            anchor="nw",
        )
        self.feedback_label.pack(
            side="bottom",
            fill="both",
            expand=True,
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


    def start_query(self, prompt):
        selected_files = self.controller.selected_files
        export_path = self.controller.export_path


        messagebox.showinfo("Submitted", f"Prompt: {prompt}\nFiles: {len(selected_files)} added.")

        try:
            config = Config()
            config.output_mode = "file"
            config.output_file = os.path.join(export_path, "REPLACE_FILENAME.xlsx")

            agent = SheetHero(
                excel_paths=selected_files,
                config=config
            )
            result = agent.run(
                user_question=prompt
            )

            result_text = f"""
                Success: {'✅' if result['success'] else '❌'}
                Answer: {result['answer']}
                Confidence: {result['confidence_score']:.2f}/1.0
                Iterations: {result['total_iterations']}
                Duration: {result['total_duration']:.2f}s
                """
            if result['issues_found']:
                result_text += "\nIssues Found:\n" + "\n".join([f" - {i}" for i in result['issues_found']])
            if result.get('improvement_feedback'):
                result_text += f"\n\nImprovement Feedback:\n{result['improvement_feedback']}"

            self.feedback_label.configure(text=f"{result_text}")

        except Exception as error:
            self.feedback_label.configure(text=f"Error: {error}")
