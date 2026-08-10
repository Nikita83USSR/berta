import json
import shlex
import subprocess

from interface.terminal_ui import ui_print, ui_status


def execute_function(name, arguments):

    print()

    ui_print(
        f"[BERTA] -> Вызов инструмента: {name}",
        bright=True
    )


    if arguments:

        ui_status(
            "АРГУМЕНТЫ",
            json.dumps(
                arguments,
                ensure_ascii=False
            )
        )


    try:

        # ===============================
        # SYSTEM COMMAND
        # ===============================

        if name == "execute_system_command":


            command = arguments.get(
                "command"
            )


            dangerous_patterns = [
                "rm -rf",
                "dd if=",
                "> /dev/",
                "mkfs.",
                "fdisk",
                "parted",
                "shutdown",
                "reboot",
                "init 0",
                "poweroff"
            ]


            cmd_lower = command.lower()


            dangerous = any(
                x in cmd_lower
                for x in dangerous_patterns
            )


            if dangerous:

                ui_print(
                    "[BERTA] ВНИМАНИЕ: Опасная операция!",
                    bright=True,
                    color="red"
                )


                confirm = input(
                    "Подтвердите выполнение (Y/y): "
                )


                if confirm.lower() != "y":

                    return {
                        "success": False,
                        "error": "Отказано пользователем"
                    }



            args = shlex.split(command)


            result = subprocess.run(

                args,

                stdout=subprocess.PIPE,

                stderr=subprocess.PIPE,

                text=True,

                timeout=60
            )


            return {

                "success": True,

                "stdout":
                    result.stdout.strip(),

                "stderr":
                    result.stderr.strip()

            }



        # ===============================
        # READ FILE
        # ===============================

        elif name == "read_file":


            filename = arguments.get(
                "filename"
            )


            with open(
                filename,
                "r",
                encoding="utf-8"
            ) as f:


                return {

                    "success": True,

                    "file": filename,

                    "code": f.read()

                }



        else:

            return {

                "success": False,

                "error":
                "Неизвестная функция: "
                + str(name)

            }



    except Exception as e:


        ui_print(
            "[BERTA] Ошибка инструмента: "
            + str(e),
            bright=True,
            color="red"
        )


        return {

            "success": False,

            "error": str(e)

        }
