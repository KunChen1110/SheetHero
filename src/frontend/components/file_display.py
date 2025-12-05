import customtkinter as ctk

from frontend.components.colors import *
from frontend.components.images import EXCEL_ICON

class FileDisplay(ctk.CTkFrame):
    def __init__(self, master, text, command):
        super().__init__(
            master=master,
            corner_radius=10,
            height=45,
            fg_color=VERY_DARK_GREY
        )

        self.file_label = ctk.CTkLabel(
            master=self,
            anchor="w",
            compound="left",
            image=EXCEL_ICON,
            text=text,
            padx=10,
        )
        self.file_label.pack(
            expand=True,
            side="left",
            fill="x",
            padx=5,
            pady=5
        )

        self.remove_button = ctk.CTkButton(
            master=self,
            text="🗑",
            width=30,
            height=30,
            command=command
        )
        self.remove_button.pack(
            side="right",
            padx=5
        )

        self.pack_propagate(False)
