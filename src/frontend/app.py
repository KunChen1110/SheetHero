import customtkinter as ctk
from tkinterdnd2 import TkinterDnD

from pages.upload_page import UploadPage
from pages.config_page import ConfigPage

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        self.title("SheetHero UI")
        self.geometry("720x480")
        self.resizable(False, False)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        self.pages = {}

        for page in (UploadPage,ConfigPage):
            page_name = page.__name__
            page = page(container, self)
            self.pages[page_name] = page
            container.rowconfigure(0, weight=1)
            container.columnconfigure(0, weight=1)
            page.grid(row=0, column=0, sticky="nsew")

        self.show_page("UploadPage")

    def show_page(self, page_name):
        page = self.pages[page_name]
        page.tkraise()


if __name__ == "__main__":
    try:
        App().mainloop()
    except KeyboardInterrupt:
        pass