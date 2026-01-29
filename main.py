import os
import sys

# This is a bit of a hack, but it works
PROJECT_ROOT = os.path.dirname(__file__)
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from frontend.app import App

if __name__ == "__main__":
    App().mainloop()