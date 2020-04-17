import os
import subprocess

def shell_await(cmd, env=None):
    if env is None:
        env = {}
    else:
        env = dict(os.environ, **env)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)

    def output():
        while True:
            line = p.stdout.readline()
            if not line:
                break
            yield str(line.rstrip())

    return p.wait(), output()