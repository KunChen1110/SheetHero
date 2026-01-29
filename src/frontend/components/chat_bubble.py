import customtkinter as ctk

class ChatBubble(ctk.CTkFrame):
    def __init__(self, master, text: str, color: str):
        super().__init__(
            master,
            height=65,
            fg_color=color
        )

        self.label = ctk.CTkLabel(
            master=self,
            text=text,
            wraplength=350,
            anchor="w",
            justify="left"
        )
        self.label.pack(
            padx=10,
            pady=10,
            fill="x"
        )