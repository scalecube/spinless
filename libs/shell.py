import os
import subprocess
from io import StringIO


class Result:
    def __init__(self, code, stdout):
        self.code = code
        self.stdout = stdout

    def code(self):
        return self.code

    def stdout(self):
        return self.stdout


def shell_await(cmd, env=None):
    if env is None:
        env = {}
    else:
        env = dict(os.environ, **env)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    string_output = StringIO()

    for c in iter(lambda: p.stdout.read(1), b''):  # replace '' with b'' for Python 3
        string_output.write(c.decode("utf-8"))

    return Result(p.wait(), string_output.getvalue())
