import customtkinter as ctk

MIN_TURNS = 1
MAX_TURNS = 10

options = ["Op1","Op2","Op3"]

class ConfigPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Button Frame
        self.button_frame = None
        self.back_button = None
        self.confirm_button = None
        self.create_button_frame()

        # API Frame
        self.api_frame = None
        self.api_label = None
        self.api_entry = None
        self.create_api_frame()

        # URL Frame
        self.url_frame = None
        self.url_label = None
        self.url_entry = None
        self.create_url_frame()

        # Deployment Frame
        self.deployment_frame = None
        self.deployment_label = None
        self.deployment_drop = None
        self.create_deployment_frame()

        # Turns Frame
        self.turns_frame = None
        self.turns_label = None
        self.turns_number = None
        self.turns_add = None
        self.turns_minus = None
        self.create_turns_frame()


    # Creates the api frame
    def create_api_frame(self):
        # =-=-= API Frame =-=-=
        self.api_frame = ctk.CTkFrame(
            master=self,
            height=40,
        )
        self.api_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=(30,5),
        )

        # =-=-= API Label =-=-=
        self.api_label = ctk.CTkLabel(
            master=self.api_frame,
            text="API Key*",
            anchor="w",
        )
        self.api_label.pack(
            side="left",
            anchor="w",
            padx=(20,0),
        )

        # =-=-= API Entry =-=-=
        self.api_entry = ctk.CTkEntry(
            master=self.api_frame,
            placeholder_text="Enter API key..."
        )
        self.api_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=20,
        )

    # Creates the url frame
    def create_url_frame(self):
        # =-=-= URL Frame =-=-=
        self.url_frame = ctk.CTkFrame(
            master=self,
            height=40,
        )
        self.url_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=5,
        )

        # =-=-= URL Label =-=-=
        self.url_label = ctk.CTkLabel(
            master=self.url_frame,
            text="Base URL",
            anchor="w",
        )
        self.url_label.pack(
            side="left",
            anchor="w",
            padx=(20,0),
        )

        # =-=-= URL Entry =-=-=
        self.url_entry = ctk.CTkEntry(
            master=self.url_frame,
            placeholder_text="Enter base URL..."
        )
        self.url_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=20,
        )


    # Creates the deployment frame
    def create_deployment_frame(self):
        # =-=-= Deployment Frame =-=-=
        self.deployment_frame = ctk.CTkFrame(
            master=self,
            height=40,
        )
        self.deployment_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=5,
        )

        # =-=-= Deployment Label =-=-=
        self.deployment_label = ctk.CTkLabel(
            master=self.deployment_frame,
            text="Deployment*",
            anchor="w",
        )
        self.deployment_label.pack(
            side="left",
            anchor="w",
            padx=(20,0),
        )

        # =-=-= Deployment Drop =-=-=
        self.deployment_drop = ctk.CTkOptionMenu(
            master=self.deployment_frame,
            values=options,
        )
        self.deployment_drop.pack(
            fill="x",
            expand=True,
            padx=20,
        )


    # Creates the turns frame
    def create_turns_frame(self):
        # =-=-= Turns Frame =-=-=
        self.turns_frame = ctk.CTkFrame(
            master=self,
            height=40,
        )
        self.turns_frame.pack(
            side="top",
            fill="x",
            padx=30,
            pady=5,
        )

        # =-=-= Turns Label =-=-=
        self.turns_label = ctk.CTkLabel(
            master=self.turns_frame,
            text="Max Turns*",
            anchor="w",
        )
        self.turns_label.pack(
            side="left",
            anchor="w",
            padx=(20,0),
        )

        # =-=-= Turns Number =-=-=
        self.turns_number = ctk.CTkLabel(
            master=self.turns_frame,
            text=f"{self.controller.max_turns}",
            anchor="w",
        )
        self.turns_number.pack(
            side="left",
            anchor="w",
            padx=(20,0)
        )

        # =-=-= Turns Add Button =-=-=
        self.turns_add = ctk.CTkButton(
            master=self.turns_frame,
            text="+",
            command=self.on_add_pressed,
            anchor="w",
        )
        self.turns_add.pack(
            side="left",
            anchor="w",
            padx=(20,0)
        )

        # =-=-= Turns Minus Button =-=-=
        self.turns_minus = ctk.CTkButton(
            master=self.turns_frame,
            text="-",
            command=self.on_minus_pressed,
            anchor="w"
        )
        self.turns_minus.pack(
            side="left",
            anchor="w",
            padx=(20,0)
        )

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
        self.confirm_button = ctk.CTkButton(
            master=self.button_frame,
            text="Confirm",
            fg_color="green",
            hover_color="gray25",
            height=40,
            command=self.on_confirm_pressed
        )
        self.confirm_button.pack(
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

    def update_turns_number(self):
        self.turns_number.configure(text=f"{self.controller.max_turns}")


    # Triggered when the add button is pressed
    def on_add_pressed(self):
        self.controller.max_turns = min(self.controller.max_turns + 1, MAX_TURNS)
        self.update_turns_number()


    # Triggered when the minus button is pressed
    def on_minus_pressed(self):
        self.controller.max_turns = max(self.controller.max_turns - 1, MIN_TURNS)
        self.update_turns_number()


    # Triggered when the back button is pressed
    def on_back_pressed(self):
        self.controller.show_page("UploadPage")

     # Triggered when the confirm button is pressed
    def on_confirm_pressed(self):
        # TODO, add checking for input boxes here
        self.controller.show_page("PromptPage")