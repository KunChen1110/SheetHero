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

selected_files = []
settings_visible = False

def add_file():
    if(len(selected_files) >= 5):
        messagebox.showerror("Error", "You can only add up to 5 files.")
        return
   
    file_path = filedialog.askopenfilename(
        title="Select an Excel file",
        filetypes=[("Excel files", "*.xlsx *.xls *.ods")]
    )
   
    if(file_path and file_path.lower().endswith(('.xlsx', '.xls', '.ods'))):
        selected_files.append(file_path)
        update_file_list()
    elif(file_path):
        messagebox.showerror("Invalid File", "Please select an Excel file (.xlsx, .xls, or .ods).")

def remove_file(index):
    if(index < len(selected_files)):
        selected_files.pop(index)
        update_file_list()

def update_file_list():
    for widget in file_list_frame.winfo_children():
        widget.destroy()

    row_height = 45
    max_files = 5
    max_chars = 35

    for i in range(max_files):
        file_row = ctk.CTkFrame(file_list_frame, corner_radius=10, height=row_height)
        file_row.pack(fill="x", pady=2, padx=5)
        file_row.pack_propagate(False)

        if(i < len(selected_files)):
            file_name = os.path.basename(selected_files[i])
            if(len(file_name) > max_chars):
                file_name = file_name[:max_chars-3] + "…"

            file_label = ctk.CTkLabel(file_row, text=file_name, anchor="w")
            file_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            bin_button = ctk.CTkButton(file_row, text="🗑", width=30, height=30,
                                       command=lambda idx=i: remove_file(idx))
            bin_button.pack(side="right", padx=5)
        else:
            placeholder_text_label = ctk.CTkLabel(
                file_row,
                text="Drag & drop Excel files here or click to browse",
                anchor="center",
                text_color="gray"
            )
            placeholder_text_label.pack(fill="both", expand=True, padx=5, pady=5)
            placeholder_text_label.bind("<Button-1>", lambda e: add_file())

def submit_prompt():
    prompt = prompt_entry.get("1.0", "end-1c").strip()
    start_query()
   
    if(not prompt or prompt == placeholder_text):
        messagebox.showwarning("Warning", "Please enter a prompt.")
        return
   
    messagebox.showinfo("Submitted", f"Prompt: {prompt}\nFiles: {len(selected_files)} added.")

def on_focus_in(event):
    if(prompt_entry.get("1.0", "end-1c").strip() == placeholder_text):
        prompt_entry.delete("1.0", "end")
        if(ctk.get_appearance_mode() == "Dark"):
            prompt_entry.configure(text_color="white")
        else:
            prompt_entry.configure(text_color="black")

def on_focus_out(event):
    if(not prompt_entry.get("1.0", "end-1c").strip()):
        prompt_entry.insert("1.0", placeholder_text)
        prompt_entry.configure(text_color="gray")

def start_query():
    print("Hello World")

def on_drop(event):
    dropped_files = root.splitlist(event.data)
   
    for file_path in dropped_files:
        file_path = file_path.strip("{}")
       
        if(not file_path.lower().endswith(('.xlsx', '.xls', '.ods'))):
            messagebox.showerror("Invalid File", f"'{file_path}' is not an Excel file.")
            continue
       
        if(len(selected_files) >= 5):
            messagebox.showerror("Error", "You can only add up to 5 files.")
            break
       
        if(file_path not in selected_files):
            selected_files.append(file_path)
   
    update_file_list()

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

def toggle_settings():
    global settings_visible
   
    if(settings_visible):
        settings_frame.place_forget()
        settings_visible = False
    else:
        settings_frame.place(x=root.winfo_width() - 220, y=60)
        settings_frame.lift()
        settings_visible = True

def on_resize(event):
    if(settings_visible):
        settings_frame.place(x=root.winfo_width() - 220, y=60)

placeholder_text = "Enter prompt here"

top_frame = ctk.CTkFrame(root, corner_radius=0, height=50)
top_frame.pack(fill="x", padx=0, pady=0)

title_label = ctk.CTkLabel(top_frame, text="Our amazing app", font=ctk.CTkFont(size=16, weight="bold"))
title_label.pack(side="left", padx=20, pady=10)

settings_button = ctk.CTkButton(top_frame, text="⚙", width=40, height=40, corner_radius=10, command=toggle_settings)
settings_button.pack(side="right", padx=20, pady=5)

prompt_frame = ctk.CTkFrame(root, corner_radius=15)
prompt_frame.pack(padx=20, pady=(10,5), fill="x")

prompt_entry = ctk.CTkTextbox(prompt_frame, height=100, corner_radius=10)
prompt_entry.insert("0.0", placeholder_text)
prompt_entry.configure(text_color="gray")
prompt_entry.pack(padx=10, pady=10, fill="x")
prompt_entry.bind("<FocusIn>", on_focus_in)
prompt_entry.bind("<FocusOut>", on_focus_out)

bottom_frame = ctk.CTkFrame(root, corner_radius=15)
bottom_frame.pack(padx=20, pady=10, fill="x", expand=True)

dnd_frame = ctk.CTkFrame(bottom_frame, corner_radius=10)
dnd_frame.pack(side="left", padx=10, pady=10, fill="both", expand=True)

file_list_frame = ctk.CTkFrame(dnd_frame)
file_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
update_file_list()

file_list_frame.drop_target_register(DND_FILES)
file_list_frame.dnd_bind('<<Drop>>', on_drop)

go_button = ctk.CTkButton(bottom_frame, text="GO", width=100, height=50, corner_radius=20, command=submit_prompt)
go_button.pack(side="right", padx=10, pady=10)

settings_frame = ctk.CTkFrame(root, corner_radius=15, width=200, height=120, border_width=0)

toggle_label = ctk.CTkLabel(settings_frame, text="Settings", font=ctk.CTkFont(size=14, weight="bold"))
toggle_label.pack(pady=(10, 5))

mode_toggle = ctk.CTkButton(settings_frame, text="Toggle Mode", command=toggle_mode)
mode_toggle.pack(pady=5)

root.bind('<Configure>', on_resize)

root.mainloop()