from importlib import resources
from customtkinter import CTkImage
from PIL import Image

def load_icon(filename, size=(20, 20)):
    with resources.path("frontend.resources", filename) as icon_path:
        img = Image.open(icon_path).resize(size)
    return CTkImage(img, size=size)


EXCEL_ICON = load_icon("xls.png")
ADD_ICON = load_icon("add.png")
DIRECTORY_ICON = load_icon("folder.png")