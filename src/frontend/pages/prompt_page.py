import customtkinter as ctk

class PromptPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Finish Button
        self.button_frame = None
        self.finish_button = None
        self.back_button = None
        self.create_button_frame()



    def create_button_frame(self):
        # =-=-= Button Frame =-=-=
        self.button_frame = ctk.CTkFrame(
            master=self,
            fg_color="transparent"
        )
        self.button_frame.pack(
            side="bottom",
            fill="x",
            pady=(0,20),
            padx=30
        )

        # =-=-= Confirm Button =-=-=
        self.finish_button = ctk.CTkButton(
            master=self.button_frame,
            text="Confirm",
            fg_color="green",
            hover_color="gray25",
            height=40,
            command=self.on_finish_pressed
        )
        self.finish_button.pack(
            side="right",
        )

        # =-=-= Confirm Button =-=-=
        self.back_button = ctk.CTkButton(
            master=self.button_frame,
            text="Back",
            fg_color="green",
            hover_color="gray25",
            height=40,
            command=self.on_back_pressed
        )
        self.back_button.pack(
            side="left",
        )

    # Triggered when the back button is pressed
    def on_back_pressed(self):
        self.controller.show_page("ConfigPage")


     # Triggered when the finish button is pressed
    def on_finish_pressed(self):
        if not self.controller.selected_files:
            # messagebox.showwarning("Warning", "Please upload the files to query on")
            return

        self.controller.show_page("UploadPage")