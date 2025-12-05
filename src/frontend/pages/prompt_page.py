import customtkinter as ctk
import os

from importlib import resources
from customtkinter import CTkImage
from PIL import Image

with resources.path("frontend.resources","xls.png") as icon_path:
    excel_img = Image.open(icon_path).resize((20,20))
excel_icon = CTkImage(excel_img, size=(20,20))


class PromptPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Finish Button
        self.button_frame = None
        self.finish_button = None
        self.back_button = None
        self.create_button_frame()

        # Data Frame
        self.data_display_frame = None
        self.feedback_label = None
        self.prompt_entry = None
        self.create_data_display_frame()

        # File Display Frame
        self.file_list_frame = None
        self.scroll_frame = None
        self.create_file_list_frame()


    def on_show(self):
        self.update_file_list()


    # Creates the data display frame
    def create_data_display_frame(self):
        # =-=-= Data Display Frame =-=-=
        self.data_display_frame = ctk.CTkFrame(
            master=self,
            width=300,
        )
        self.data_display_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(30,5),
            pady=20,
        )

        # =-=-= Prompt Entry =-=-=
        self.prompt_entry = ctk.CTkTextbox(
            master=self.data_display_frame,
            height=100,
        )
        self.prompt_entry.pack(
            side="top",
            fill="both",
            padx=5,
            pady=(5,10),
        )

        # =-=-= Feedback Label =-=-=
        self.feedback_label = ctk.CTkLabel(
            master=self.data_display_frame,
            fg_color="gray16",
            text="Feedback",
            anchor="nw",
        )
        self.feedback_label.pack(
            side="bottom",
            fill="both",
            expand=True,
            padx=5,
            pady=5,
        )


    # Creates the file display frame
    def create_file_list_frame(self):
        self.file_list_frame = ctk.CTkFrame(
            master=self,
        )
        self.file_list_frame.pack(
            side="right",
            fill="both",
            padx=(5,30),
            pady=20,
        )

        self.scroll_frame = ctk.CTkScrollableFrame(
            master=self.file_list_frame,
            orientation="vertical"
        )
        self.scroll_frame.pack(
            expand=True,
            fill="both",
            padx=5,
            pady=5,
        )


    # Creates the button frame
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


    def update_file_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for i in range(len(self.controller.selected_files)):
            print("test")
            file_row = ctk.CTkFrame(
                self.scroll_frame,
                corner_radius=10,
                height=45,
                fg_color="gray14"
            )
            file_row.pack(
                fill="x",
                pady=2,
                padx=2
            )
    
            file_row.pack_propagate(False)
            file_name = os.path.basename(self.controller.selected_files[i])
    
            file_label = ctk.CTkLabel(
                file_row,
                anchor="w",
                compound="left",
                image=excel_icon,
                text=f"#{i+1} {file_name}",
                padx=10,
            )
            file_label.pack(
                expand=True,
                side="left",
                fill="x",
                padx=5,
                pady=5
            )
    
            bin_button = ctk.CTkButton(
                file_row,
                text="🗑",
                width=30,
                height=30,
                # command=lambda index=i: self.remove_file(index)
            )
            bin_button.pack(
                side="right",
                padx=5
            )

    # Triggered when the back button is pressed
    def on_back_pressed(self):
        self.controller.show_page("ConfigPage")


     # Triggered when the finish button is pressed
    def on_finish_pressed(self):
        # TODO Link backend here
        self.controller.show_page("UploadPage")