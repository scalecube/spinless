import asyncio

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


async def run(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE):
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout, stderr)

    stdout, stderr = await proc.communicate()
    return Result(await proc.wait(),
                  stdout,
                  stderr)


def shell_await(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE):
    return loop.run_until_complete(asyncio.gather(
        run(cmd, stdout, stderr)
    ))[0]
