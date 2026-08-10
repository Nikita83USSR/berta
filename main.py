import json
from core.brain import BertaBrain
from core.memory import Memory
from core.personality import BERTA_PERSONALITY

from interface.terminal_ui import (
    show_boot_screen,
    ui_status,
    ui_print
)

from tools.functions import FUNCTIONS
from tools.function_manager import execute_function



def main():

    show_boot_screen()


    ui_status(
        "BRAIN",
        "ЗАГРУЗКА"
    )


    brain = BertaBrain()


    ui_status(
        "GIGA",
        "READY"
    )


    memory = Memory()


    memory.add(
        "system",
        BERTA_PERSONALITY
    )


    ui_status(
        "MEMORY",
        "READY"
    )


    print()


    ui_print(
        "BERTA 0.1 ONLINE",
        bright=True,
        color="green"
    )


    while True:


        try:

            user = input(
                "\nВЫ: "
            )


            if user.lower() in [
                "exit",
                "quit",
                "выход"
            ]:
                break



            memory.add(
                "user",
                user
            )


            ui_status(
                "THINK",
                "ANALYSIS"
            )


            result = brain.ask(
                memory.get(),
                FUNCTIONS
            )


            message = result[
                "choices"
            ][0][
                "message"
            ]



            # если GigaChat попросил инструмент

            if "function_call" in message:


                function_call = message[
                    "function_call"
                ]


                name = function_call[
                    "name"
                ]


                arguments = json.loads(
                    function_call["arguments"]
                )


                tool_result = execute_function(
                    name,
                    arguments
                )


                memory.add(
                    "function",
                    str(tool_result)
                )


                result = brain.ask(
                    memory.get()
                )


                message = result[
                    "choices"
                ][0][
                    "message"
                ]



            answer = message.get(
                "content",
                ""
            )


            memory.add(
                "assistant",
                answer
            )


            ui_status(
                "ANSWER",
                "READY"
            )


            print()


            ui_print(
                "БЕРТА:",
                bright=True,
                color="green"
            )


            print(answer)



        except Exception as e:


            ui_print(
                "ОШИБКА: " + str(e),
                bright=True,
                color="red"
            )



if __name__ == "__main__":

    main()
