import customtkinter as ctk

from frontend.components.colors import *
from frontend.components.images import FILE_ICON, REMOVE_ICON


class FileDisplay(ctk.CTkFrame):
    def __init__(self, master, text, command):
        super().__init__(
            master=master,
            corner_radius=10,
            height=45,
            fg_color=VERY_DARK_GREY
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        self.file_label = ctk.CTkLabel(
            master=self,
            anchor="w",
            compound="left",
            image=FILE_ICON,
            text=text,
            padx=10,
        )
        self.file_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=5,
            pady=5,
        )

        self.remove_button = ctk.CTkButton(
            master=self,
            image=REMOVE_ICON,
            text="",
            width=25,
            height=25,
            fg_color=RED,
            hover_color=HOVER_RED,
            command=command
        )
        self.remove_button.grid(
            row=0,
            column=1,
            padx=5,
        )

        self.pack_propagate(False)
