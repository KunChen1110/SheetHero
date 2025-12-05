from tkinter import messagebox
from typing import List

import customtkinter as ctk

from frontend.components.colors import *
from frontend.components.footer_frame import FooterFrame

MIN_TURNS: int = 1
MAX_TURNS: int = 10

options: List[str] = [
    "gpt-4o-mini",
    "gpt-4-32k",
    "gpt-4",
    "gpt-4o",
]

from frontend.components.colors import GREEN

class ConfigPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Main Label
        self.main_label = None
        self.create_main_label()

        # Footer
        self.footer = None
        self.back_button = None
        self.confirm_button = None
        self.create_footer()

        # API Frame
        self.api_frame = None
        self.api_label = None
        self.api_entry = None
        self.api_description = None
        self.create_api_frame()

        # URL Frame
        self.url_frame = None
        self.url_label = None
        self.url_entry = None
        self.url_description = None
        self.create_url_frame()

        # Deployment Frame
        self.deployment_frame = None
        self.deployment_label = None
        self.deployment_drop = None
        self.deployment_description = None
        self.create_deployment_frame()

        # Turns Frame
        self.turns_frame = None
        self.turns_label = None
        self.turns_spin = None
        self.turns_number = None
        self.turns_add = None
        self.turns_minus = None
        self.turns_description = None
        self.create_turns_frame()

    # Creates the main label
    def create_main_label(self):
        # =-=-= Main Label =-=-=
        self.main_label = ctk.CTkLabel(
            master=self,
            text="Configuration Settings",
            font=("tkDefaultFont",20)
        )
        self.main_label.pack(
            side="top",
            anchor="w",
            padx=20,
            pady=(10,5),
        )


    # Creates the api frame
    def create_api_frame(self):
        # =-=-= API Frame =-=-=
        self.api_frame = ctk.CTkFrame(
            master=self,
            height=40,
            fg_color="transparent",
        )
        self.api_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=(5,2),
        )

        # =-=-= API Label =-=-=
        self.api_label = ctk.CTkLabel(
            master=self.api_frame,
            text="API Key",
            anchor="w",
        )
        self.api_label.pack(
            side="top",
            anchor="w",
            padx=20,
        )

        # =-=-= API Entry =-=-=
        self.api_entry = ctk.CTkEntry(
            master=self.api_frame,
            placeholder_text="Enter API key...",
            fg_color=MID_GREY,
            border_width=0,
        )
        self.api_entry.pack(
            side="top",
            fill="x",
            expand=True,
            padx=20,
        )

        # =-=-= API Description =-=-=
        self.api_description = ctk.CTkLabel(
            master=self.api_frame,
            text="Enter your api key for Open AI",
            text_color=VERY_LIGHT_GREY,
            anchor="w",
        )
        self.api_description.pack(
            side="top",
            fill="x",
            padx=20,
        )

    # Creates the url frame
    def create_url_frame(self):
        # =-=-= URL Frame =-=-=
        self.url_frame = ctk.CTkFrame(
            master=self,
            height=40,
            fg_color="transparent",
        )
        self.url_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=2,
        )

        # =-=-= URL Label =-=-=
        self.url_label = ctk.CTkLabel(
            master=self.url_frame,
            text="Base URL (Optional)",
            anchor="w",
        )
        self.url_label.pack(
            side="top",
            anchor="w",
            padx=20,
        )

        # =-=-= URL Entry =-=-=
        self.url_entry = ctk.CTkEntry(
            master=self.url_frame,
            placeholder_text="Enter Base URL...",
            fg_color=MID_GREY,
            border_width=0,
        )
        self.url_entry.pack(
            side="top",
            fill="x",
            expand=True,
            padx=20,
        )

        # =-=-= URL Description =-=-=
        self.url_description = ctk.CTkLabel(
            master=self.url_frame,
            text="Enter your base URL",
            text_color=VERY_LIGHT_GREY,
            anchor="w",
        )
        self.url_description.pack(
            side="top",
            fill="x",
            padx=20,
        )


    # Creates the deployment frame
    def create_deployment_frame(self):
        # =-=-= Deployment Frame =-=-=
        self.deployment_frame = ctk.CTkFrame(
            master=self,
            height=40,
            fg_color="transparent",
        )
        self.deployment_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=2,
        )

        # =-=-= Deployment Label =-=-=
        self.deployment_label = ctk.CTkLabel(
            master=self.deployment_frame,
            text="Deployment",
            anchor="w",
        )
        self.deployment_label.pack(
            side="top",
            anchor="w",
            padx=20,
        )

        # =-=-= Deployment Drop =-=-=
        self.deployment_drop = ctk.CTkOptionMenu(
            master=self.deployment_frame,
            fg_color=MID_GREY,
            button_color=VERY_DARK_GREY,
            values=options,
        )
        self.deployment_drop.pack(
            side="top",
            fill="x",
            expand=True,
            padx=20,
        )

        # =-=-= Deployment Description =-=-=
        self.deployment_description = ctk.CTkLabel(
            master=self.deployment_frame,
            text="Enter the Open AI model used to calculate results",
            text_color=VERY_LIGHT_GREY,
            anchor="w",
        )
        self.deployment_description.pack(
            side="top",
            fill="x",
            padx=20,
        )


    # Creates the turns frame
    def create_turns_frame(self):
        # =-=-= Turns Frame =-=-=
        self.turns_frame = ctk.CTkFrame(
            master=self,
            height=40,
            fg_color="transparent",
        )
        self.turns_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=2,
        )

        # =-=-= Turns Label =-=-=
        self.turns_label = ctk.CTkLabel(
            master=self.turns_frame,
            text="Max Turns",
            anchor="w",
        )
        self.turns_label.pack(
            side="top",
            anchor="w",
            padx=20,
        )

        # =-=-= Turns Spin Box =-=-=
        self.turns_spin = ctk.CTkFrame(
            master=self.turns_frame,
            fg_color=MID_GREY,
        )
        self.turns_spin.pack(
            expand=True,
            side="top",
            fill="x",
            padx="20",
        )

        # =-=-= Turns Number =-=-=
        self.turns_number = ctk.CTkLabel(
            master=self.turns_spin,
            text=f"{self.controller.max_turns}",
            anchor="w",
        )
        self.turns_number.pack(
            expand=True,
            side="left",
            fill="x",
            anchor="w",
            padx=10,
            pady=2,
        )

        # =-=-= Turns Minus Button =-=-=
        self.turns_minus = ctk.CTkButton(
            master=self.turns_spin,
            text="-",
            fg_color=VERY_DARK_GREY,
            command=self.on_minus_pressed,
            height=25,
            width=25
        )
        self.turns_minus.pack(
            side="right",
            padx=(2,20),
        )

        # =-=-= Turns Add Button =-=-=
        self.turns_add = ctk.CTkButton(
            master=self.turns_spin,
            text="+",
            fg_color=VERY_DARK_GREY,
            command=self.on_add_pressed,
            height=25,
            width=25
        )
        self.turns_add.pack(
            side="right",
            padx=2,
        )

        # =-=-= Deployment Description =-=-=
        self.deployment_description = ctk.CTkLabel(
            master=self.turns_frame,
            text="Enter the max-amount of interaction turns in the model",
            text_color=VERY_LIGHT_GREY,
            anchor="w",
        )
        self.deployment_description.pack(
            side="top",
            fill="x",
            padx=20,
        )


    # Creates the footer
    def create_footer(self):
        # =-=-= Footer =-=-=
        self.footer = FooterFrame(master=self)

        # =-=-= Confirm Button =-=-=
        self.confirm_button = ctk.CTkButton(
            master=self.footer,
            text="Confirm",
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            height=40,
            command=self.on_confirm_pressed
        )
        self.confirm_button.pack(
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

    # Updates the turns amount number
    def update_turns_number(self):
        self.turns_number.configure(text=f"{self.controller.max_turns}")


    # Triggered when the add button is pressed
    def on_add_pressed(self):
        self.controller.max_turns = min(self.controller.max_turns + 1, MAX_TURNS)
        self.update_turns_number()


    # Triggered when the minus button is pressed
    def on_minus_pressed(self):
        self.controller.max_turns = max(self.controller.max_turns - 1, MIN_TURNS)
        self.update_turns_number()


    # Triggered when the back button is pressed
    def on_back_pressed(self):
        self.controller.show_page("UploadPage")


     # Triggered when the confirm button is pressed
    def on_confirm_pressed(self):
        api_key = self.api_entry.get().strip()

        if not api_key:
            messagebox.showwarning("Warning","Please enter an API key.")
            return


        self.controller.api_key = api_key
        self.controller.base_url = self.url_entry.get().strip()
        self.controller.deployment = self.deployment_drop.get()

        self.controller.show_page("PromptPage")