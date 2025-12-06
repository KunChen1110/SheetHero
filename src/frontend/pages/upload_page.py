import customtkinter as ctk
import os

from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES

from frontend.components.colors import *
from frontend.components.file_display import FileDisplay
from frontend.components.images import ADD_ICON, DIRECTORY_ICON
from frontend.components.footer_frame import FooterFrame


class UploadPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Header
        self.header = None
        self.header_text = None
        self.export_button = None
        self.file_button = None
        self.directory_button = None
        self.create_header()

        # Scroll Frame
        self.drop_frame = None
        self.scroll_frame = None
        self.create_scroll_frame()

        # Footer
        self.footer = None
        self.upload_button = None
        self.create_footer()

    # Updates the file list when menu is visible
    def on_show(self):
        self.update_file_list()


    # Creates the header
    def create_header(self):
        # =-=-= Header =-=-=
        self.header = ctk.CTkFrame(
            master=self,
            height=40,
            fg_color=DARK_GREY,
        )
        self.header.pack(
            fill="x",
            side="top",
            padx=30,
            pady=(20,0),
        )

        # =-=-= File Button =-=-=
        self.file_button = ctk.CTkButton(
            master=self.header,
            text="",
            image=ADD_ICON,
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            width=30,
            command=self.browse_files
        )
        self.file_button.pack(
            side="left",
            fill="y",
            padx=5,
            pady=5,
        )

        # =-=-= Directory Button =-=-=
        self.directory_button = ctk.CTkButton(
            master=self.header,
            text="",
            image=DIRECTORY_ICON,
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            width=30,
            command=self.choose_export_folder
        )
        self.directory_button.pack(
            side="left",
            fill="y",
            padx=5,
            pady=5,
        )

        # =-=-= Header Text =-=-=
        self.header_text = ctk.CTkLabel(
            master=self.header,
            text=f"Saving to {self.controller.export_path}",
        )
        self.header_text.pack(
            side="left",
            fill="x",
            padx=5,
            pady=5,
        )

        self.header.pack_propagate(False)


    # Creates the scroll frame
    def create_scroll_frame(self):
        # =-=-= Drop Frame =-=-=
        # Invisible drop frame to catch files
        self.drop_frame = ctk.CTkFrame(
            master=self,
            height=450,
            fg_color="transparent"
        )
        self.drop_frame.pack(
            expand=True,
            fill="both",
            padx=30,
            pady=20,
        )

        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>',self.on_drop)

        # =-=-= Scroll Frame =-=-=
        self.scroll_frame = ctk.CTkScrollableFrame(
            master=self.drop_frame,
            orientation="vertical",
            border_width=5,
            border_color=VERY_DARK_GREY,
        )
        self.scroll_frame.pack(
            expand=True,
            fill="both",
        )


    def create_footer(self):
        # =-=-= Footer =-=-=
        self.footer = FooterFrame(master=self)

        # =-=-= Upload Button =-=-=
        self.upload_button = ctk.CTkButton(
            master=self.footer,
            text="Upload",
            fg_color=GREEN,
            hover_color=HOVER_GREEN,
            height=40,
            command=self.on_upload_pressed
        )
        self.upload_button.pack(
            side="right",
            padx=20,
        )

    # Removes a file from the selected files
    def remove_file(self,index):
        if index < len(self.controller.selected_files):
            self.controller.selected_files.pop(index)
            self.update_file_list()


    # Browses OS file explorer for .xlsx files
    def browse_files(self):
        file_paths = filedialog.askopenfilenames(
            title="Select Excel file(s)",
            filetypes=[("Excel files", "*.xlsx *.xls *.ods")]
        )

        errors = self.process_files(file_paths)
        if errors:
            messagebox.showerror("Error adding files", "\n".join(errors))

        self.update_file_list()


    # Updates the file list
    def update_file_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not self.controller.selected_files:
            placeholder = ctk.CTkLabel(
                self.scroll_frame,
                text="Drop files here or click + to add",
                text_color=WHITE,
                font=("Arial", 16),
            )
            placeholder.pack(
                expand=True,
                fill="both",
                pady=125
            )
            return

        for i in range(len(self.controller.selected_files)):
            file_name = os.path.basename(self.controller.selected_files[i])

            file_display = FileDisplay(
                self.scroll_frame,
                text=f"#{i+1} {file_name}",
                command=lambda index=i: self.remove_file(index)
            )
            file_display.pack(
                fill="x",
                pady=2,
                padx=2
            )

    # Browses OS file-explorer for export directory folder
    def choose_export_folder(self):
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.controller.export_path = folder
            self.header_text.configure(text=f"Saving to {self.controller.export_path}")


    # Triggered when dropping a file in the file list
    def on_drop(self,event):
        dropped_items = self.controller.splitlist(event.data)
        all_files = []

        for path in dropped_items:
            path = path.strip("{}")

            if os.path.isdir(path):
                for file_name in os.listdir(path):
                    file_path = os.path.join(path, file_name)
                    if os.path.isfile(file_path):
                        all_files.append(file_path)

            elif os.path.isfile(path):
                all_files.append(path)

        errors = self.process_files(all_files)
        if errors:
            messagebox.showerror("Error adding files", "\n".join(errors))

        self.update_file_list()


    # Triggered when the upload button is pressed
    def on_upload_pressed(self):
        if not self.controller.selected_files:
            messagebox.showwarning("Warning", "Please upload the files to query on")
            return

        self.controller.show_page("ConfigPage")


    def is_valid_file(self,file_path):
        if not file_path.lower().endswith(('.xlsx', '.xls', '.ods')):
            return f"{file_path} is not an Excel file."

        if file_path in self.controller.selected_files:
            return f"{file_path} has already been uploaded."

        return True


    def process_files(self,file_paths):
        error_messages = []

        for path in file_paths:
            path = path.strip("{}")
            result = self.is_valid_file(path)

            if result is True:
                self.controller.selected_files.append(path)
            else:
                error_messages.append(result)

        return error_messages