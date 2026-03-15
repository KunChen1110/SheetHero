import customtkinter as ctk
import os

from tkinterdnd2 import TkinterDnD
from typing import Optional, List

from backend import ConfigFactory
from frontend.pages.upload_page import UploadPage
from frontend.pages.config_page import ConfigPage
from frontend.pages.prompt_page import PromptPage

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        # Window variables
        self.title("SheetHero")
        self.geometry("720x480")
        self.minsize(width=720,height=480)

        # Backend variables
        frontend_defaults = ConfigFactory.get_frontend_defaults()
        self.export_path: str = os.path.join(os.path.expanduser("~"), "Documents")
        self.selected_files: List[str] = []
        self.api_key: str = str(frontend_defaults["api_key"] or "")
        self.base_url: Optional[str] = frontend_defaults["base_url"]
        self.deployment: str = str(frontend_defaults["deployment"])
        self.max_turns: int = int(frontend_defaults["max_turns"])
        self.enable_diagnose: bool = bool(frontend_defaults["enable_diagnose"])

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        self.pages = {}

        for page in (UploadPage, ConfigPage, PromptPage):
            page_name = page.__name__
            page = page(container, self)
            self.pages[page_name] = page

            container.rowconfigure(0, weight=1)
            container.columnconfigure(0, weight=1)
            page.grid(row=0, column=0, sticky="nsew")

        # Make the first page the upload page
        self.show_page("UploadPage")


    # Makes a page visible
    def show_page(self, page_name: str):
        page = self.pages[page_name]

        # Calls a page's show_page function, everytime it is seen,
        # This is used for elements that need to be refreshed per page load.
        if hasattr(page, "on_show"):
            page.on_show()

        page.tkraise()
