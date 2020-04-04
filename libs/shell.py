import asyncio
import subprocess

loop = asyncio.get_event_loop()


class Result:
    def __init__(self, code, stdout, stderr):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr

    def code(self):
        return self.code

    def stdout(self):
        return self.stdout

    def stderr(self):
        return self.stderr


def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)

    (output, err) = p.communicate()
    p_status = p.wait()

    return Result(p_status,
                  output,
                  err)


def shell_await(cmd):
    return run(cmd)

