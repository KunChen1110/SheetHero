from cgitb import reset
import enum
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
root = TkinterDnD.Tk()
root.title("GUI Prototype")
root.geometry("550x500")
root.resizable(False, False)
root.configure(background='gray14')

selected_files = []
settings_visible = False

# Checks if a file is valid
def is_valid_file(file_path):
    if(not file_path.lower().endswith(('.xlsx', '.xls', '.ods'))):
        return f"{file_path} is not an Excel file."

    if(file_path in selected_files):
        return f"{file_path} has already been uploaded."

    return True


# Adds files to the selected files list and returns errors messages if an error occurred
def process_files(file_paths):
    error_messages = []

    for path in file_paths:
        path = path.strip("{}")
        result = is_valid_file(path)

        if result is True:
            selected_files.append(path)
        else:
            error_messages.append(result)

    return error_messages


# On-drop event, detects if input is a file or a directory
# If the input(s) is a directory, it iterates through every file, then processes it
# If the input(s) is a file, it validates the files, then processes it
def on_drop(event):
    dropped_items = root.splitlist(event.data)
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

    errors = process_files(all_files)
    if errors:
        messagebox.showerror("Error adding files", "\n".join(errors))

    update_file_list()


# Opens file explorer and validates the chosen files
def browse_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Excel file(s)",
        filetypes=[("Excel files", "*.xlsx *.xls *.ods")]
    )

    errors = process_files(file_paths)
    if errors:
        messagebox.showerror("Error adding files", "\n".join(errors))

    update_file_list()


# Removes a file from the selected files list
def remove_file(index):
    if(index < len(selected_files)):
        selected_files.pop(index)
        update_file_list()


# Creates a visual frame for every file in the selected list, including its name and index
def update_file_list():
    for widget in file_scroll_list.winfo_children():
        widget.destroy()

    row_height = 45
    max_chars = 35

    for i in range(len(selected_files)):
        file_row = ctk.CTkFrame(file_scroll_list, corner_radius=10, height=row_height,fg_color="gray14")
        file_row.pack(fill="x", pady=2, padx=2)
        file_row.pack_propagate(False)

        file_name = os.path.basename(selected_files[i])
        if(len(file_name) > max_chars):
            file_name = file_name[:max_chars-3] + "…"

        file_label = ctk.CTkLabel(file_row, text=f"#{i+1}  {file_name}", anchor="w") # Adds 1 to index to make it more readable
        file_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        bin_button = ctk.CTkButton(file_row, text="🗑", width=30, height=30,command=lambda index=i: remove_file(index))
        bin_button.pack(side="right", padx=5)


# Validates all files selected and the prompt, if successful it starts the query
def submit_prompt():
    prompt = prompt_entry.get("1.0", "end-1c").strip()
   
    if(not prompt or prompt == placeholder_text):
        messagebox.showwarning("Warning", "Please enter a prompt.")
        return

    if(not selected_files):
        messagebox.showwarning("Warning", "Please upload the files to query on")
        return
   
    start_query()


# Removes the placeholder text when focused on text input
def on_focus_in(event):
    if(prompt_entry.get("1.0", "end-1c").strip() == placeholder_text):
        prompt_entry.delete("1.0", "end")
        prompt_entry.configure(text_color="white")


# Adds the placeholder text when not focused on text input
def on_focus_out(event):
    if(prompt_entry.get("1.0", "end-1c").strip() == ""):
        prompt_entry.delete("1.0", "end")
        prompt_entry.insert("1.0", placeholder_text)
        prompt_entry.configure(text_color="gray")


# Starts the query with given files and prompt
def start_query():
    prompt = prompt_entry.get("1.0", "end-1c").strip()
    messagebox.showinfo("Submitted", f"Prompt: {prompt}\nFiles: {len(selected_files)} added.")

    for i in range(len(selected_files)):
        print(f"{selected_files[i]} is index {i+1}") # These indexes will be used as reference points in prompt 


# Toggles the mode between light and dark theme
# TODO This isn't called anywhere yet
def toggle_mode():
    current_mode = ctk.get_appearance_mode()
   
    if(current_mode == "Dark"):
        ctk.set_appearance_mode("Light")
        if(prompt_entry.get("1.0", "end-1c").strip() != placeholder_text):
            prompt_entry.configure(text_color="black")
    else:
        ctk.set_appearance_mode("Dark")
        if(prompt_entry.get("1.0", "end-1c").strip() != placeholder_text):
            prompt_entry.configure(text_color="white")


# Footer, for displaying additional info
footer = ctk.CTkFrame(master=root, height=25)
footer.pack_propagate(False)
footer.pack(fill="x", side="bottom")
footer_label = ctk.CTkLabel(master=footer, text="Footer text here")
footer_label.pack(side="left",padx=(10, 0))

# Prompt entry, for inputting user prompt
placeholder_text = "Enter your prompt here..."
prompt_entry = ctk.CTkTextbox(master=root, height=0, width=320)
prompt_entry.pack(pady=(10, 10), fill="y", padx=(10, 0), side="left")
prompt_entry.insert("0.0", placeholder_text)
prompt_entry.configure(text_color="gray")
prompt_entry.pack(padx=10, pady=10)
prompt_entry.bind("<FocusIn>", on_focus_in)
prompt_entry.bind("<FocusOut>", on_focus_out)

# Go button, for beginning query
go_button = ctk.CTkButton(master=root, text="GO", compound="top", height=50, width=0,command=submit_prompt)
go_button.pack(padx=(10, 10), fill="x", pady=(0, 10), side="bottom")

# File frame, for holding the file list and file browse button
file_frame = ctk.CTkFrame(master=root, border_width=0)
file_frame.pack_propagate(False)
file_frame.pack(pady=(10, 10), expand=1, fill="y")

# Browse button, for browsing local files
browse_button = ctk.CTkButton(master=file_frame, text="Browse files", height=49, command=browse_files)
browse_button.pack(pady=(25, 0))

# File list frame, for displaying all files selected
file_list_frame = ctk.CTkFrame(master=file_frame, fg_color="transparent")
file_list_frame.pack_propagate(False)
file_list_frame.pack(pady=(10, 10), expand=1, fill="both", padx=10)
file_list_frame.drop_target_register(DND_FILES)
file_list_frame.dnd_bind('<<Drop>>',on_drop)

# Label, for drag and drop instructions
dnd_label = ctk.CTkLabel(master=file_list_frame, text="Drop documents here to upload")
dnd_label.pack()

# Scroll list, for scrolling selected files
file_scroll_list = ctk.CTkScrollableFrame(master=file_list_frame, orientation="vertical", fg_color="transparent")
file_scroll_list.pack(expand=True, fill="both", pady=(5, 0))

root.mainloop()