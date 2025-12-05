import customtkinter as ctk
import os

from tkinterdnd2 import TkinterDnD
from typing import Optional

from pages.upload_page import UploadPage
from pages.config_page import ConfigPage
from pages.prompt_page import PromptPage


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        self.title("SheetHero")
        self.geometry("720x480")
        self.resizable(False, False)

        # Backend Variables
        self.export_path: str = os.path.join(os.path.expanduser("~"), "Documents")
        self.selected_files = []
        self.api_key: str = ""
        self.base_url: Optional[str] = None
        self.deployment: str = "gpt-4o-mini"
        self.max_turns: int = 3

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        self.pages = {}

        for page in (UploadPage,ConfigPage,PromptPage):
            page_name = page.__name__
            page = page(container, self)
            self.pages[page_name] = page
            container.rowconfigure(0, weight=1)
            container.columnconfigure(0, weight=1)
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("ConfigPage") # TODO change this

    def show_page(self, page_name):
        page = self.pages[page_name]
        if hasattr(page, "on_show"):
            page.on_show()
        page.tkraise()


if __name__ == "__main__":
    App().mainloop()