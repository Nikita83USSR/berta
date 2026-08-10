# interface/terminal_ui.py


RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
GREEN = "\033[92m"
DIM_GREEN = "\033[32m"
RESET = "\033[0m"
BOLD = "\033[1m"


BERTA_ASCII = r"""
██████  ███████ ██████  ████████  █████
██   ██ ██      ██   ██    ██    ██   ██
██████  █████   ██████     ██    ███████
██   ██ ██      ██   ██    ██    ██   ██
██████  ███████ ██   ██    ██    ██   ██

        AUTONOMOUS LOCAL INTELLIGENCE
"""


def ui_print(text="", bright=False, color=None):

    if color == "red":
        prefix = RED

    elif color == "yellow":
        prefix = YELLOW

    elif color == "blue":
        prefix = BLUE

    elif color == "green":
        prefix = GREEN

    elif color == "dim_green":
        prefix = DIM_GREEN

    else:
        prefix = GREEN if bright else DIM_GREEN


    if bright and color != "red":
        prefix += BOLD


    print(
        prefix +
        str(text) +
        RESET
    )



def ui_status(label, status="OK"):

    print(
        DIM_GREEN +
        f"[ {label:<8} ]" +
        RESET +
        " " +
        GREEN +
        status +
        RESET
    )



def show_boot_screen():

    print(
        GREEN +
        BOLD +
        BERTA_ASCII +
        RESET
    )

    print()

    ui_print(
        "B E R T A   0",
        bright=True
    )

    ui_print(
        "AUTONOMOUS LOCAL INTELLIGENCE SYSTEM"
    )

    print()

    ui_status(
        "CORE",
        "ИНИЦИАЛИЗАЦИЯ"
    )
