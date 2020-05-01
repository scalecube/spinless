import os
import subprocess


def shell_await(cmd, env=None, with_output=False, cwd=None, timeout=None):
    if env:
        env = dict(os.environ, **env)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd)
    else:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)

    def output():
        if not with_output:
            yield "Command started: {}".format(cmd)
        else:
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                yield line.rstrip().decode("utf-8")

    return p.wait(timeout=timeout), output()