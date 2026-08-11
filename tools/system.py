import subprocess


def execute_system_command(command):

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )

    return {
        "stdout":result.stdout,
        "stderr":result.stderr,
        "code":result.returncode
    }



def read_file(filename):

    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()
