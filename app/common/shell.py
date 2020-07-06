import os
import shlex
import subprocess


def shell_await(cmd, env=None, with_output=False, cwd=None, timeout=300, get_stream=False):
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

    def stream():
        if not with_output:
            return None
        else:
            return p.stdout

    def output():
        if not with_output:
            yield "Command started: {}".format(cmd)
        else:
            while True:
                line = p.stdout.readline()
                if not line:
                    break
                yield line.rstrip().decode("utf-8")

    if get_stream:
        return p.wait(timeout=timeout), stream()
    else:
        return p.wait(timeout=timeout), output()


def shell_run(cmd, env=None, cwd=None, timeout=300, get_stream=False):
    """
    Execute a command in subprocess.run(...)
    :param get_stream: returns output in stream if True, as list of lines - otherwise
    :param cmd: command to execute (using subprocess.run(...))
    :param env: custom environment variables params to pass to command execution
    :param cwd: current working directory (optional)
    :param timeout: timeout to override.
    :return: exit (code, system out iterable (if any))
    """
    cmd = shlex.split(cmd)
    if env:
        env = dict(os.environ, **env)
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd,
                                   timeout=timeout)
    else:
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, timeout=timeout)

    return_code = completed.returncode
    if get_stream:
        return return_code, completed.stdout
    else:
        return return_code, completed.stdout.decode('utf-8').split('\n')
