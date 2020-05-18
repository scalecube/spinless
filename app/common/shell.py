import os
import subprocess


def shell_await(cmd, env=None, with_output=False, cwd=None, timeout=None):
    """
    Execute a command in new Subprocess (Popen(...))
    :param cmd: command to execute (using Popen)
    :param env: custom environment variables params to pass to command execution
    :param with_output: whether to return all output
    :param cwd: current working directory (optional)
    :param timeout: timeout to override. By default - Popen.wait's default value
    :return: exit (code, system out iterable (if any))
    """
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
