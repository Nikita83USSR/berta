# interface/terminal_ui.py

RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
GREEN = "\033[92m"
DIM_GREEN = "\033[32m"
RESET = "\033[0m"
BOLD = "\033[1m"


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

    print(prefix + str(text) + RESET)


def ui_status(label, status="OK"):
    print(
        DIM_GREEN + f"[ {label:<8} ]" + RESET + " " + GREEN + status + RESET
    )
