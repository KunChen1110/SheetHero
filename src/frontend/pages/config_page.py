import customtkinter as ctk

class ConfigPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label = ctk.CTkLabel(self, text="This is the Config Page", font=("Arial", 22))
        label.pack(pady=40)

        back_button = ctk.CTkButton(
            self,
            text="Go Back",
            command=lambda: controller.show_page("UploadPage")
        )
        back_button.pack(pady=20)
