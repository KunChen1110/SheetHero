import customtkinter as ctk

from frontend.components.colors import LIGHT_GREY

class FooterFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            height=65,
            fg_color=LIGHT_GREY
        )
        self.pack(
            side="bottom",
            fill="x",
        )
        self.pack_propagate(False)