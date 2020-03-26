import os
import shlex
import uuid
import asyncio
import functools
import threading
from subprocess import Popen, PIPE

jobs_dict = dict()

class Job:
    def __init__(self, cmd):
        self.id = str(uuid.uuid1())
        self.cmd = cmd
        self.status = "CREATED"
        self.proc = None
        self.code = None
        return

    def start(self):
        try:
            self.status = 'RUNNING'
            with Popen(shlex.split(self.cmd), stdout=PIPE, stderr=PIPE) as p, open(self.__log_name(), 'w') as logfile:
                s_out = p.stdout
                self.proc = p
                for line in iter(s_out.readline, b''):
                    logfile.write(line.decode("utf-8"))
                self.code = p.wait()
                self.status = 'STOPPED'
        except Exception as ex:
            self.__terminate()

    def stop(self):
        return self.__terminate()

    def get_log(self):
        def from_std(stream_to_generate):
            line = stream_to_generate.readline()
            while line:
                yield line.strip()
                line = stream_to_generate.readline()

        def from_file(filename):
            if not os.path.isfile(filename):
                return "No log was found: {}".format(filename)
            with open(filename) as f:
                line = f.readline()
                while line:
                    yield line.strip()
                    line = f.readline()

        if self.__running():
            return from_std(self.proc.stdout)
        else:
            return from_file(self.__log_name())

    def __running(self):
        return self.proc and self.proc.poll() is None

    def __terminate(self):
        if self.status == 'STOPPED':
            return False
        self.status = 'STOPPED'
        if self.__running():
            self.proc.terminate()
            return True
        else:
            return False

    def __log_name(self):
        return '{}.log'.format(self.id)


def create_job(cmd):
    job = Job(cmd)
    jobs_dict[job.id] = job
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.call_soon_threadsafe(functools.partial(job.start))
    threading.Thread(target=job.start).start()
    return job.id


def cancel_job(job_id):
    job = jobs_dict[job_id]
    if not job:
        return False
    # del jobs_dict[job_id]
    return job.stop()


def get_job_log(job_id):
    job = jobs_dict[job_id]
    if not job:
        return "no such job {}".format(job_id)
    return job.get_log()


def get_job_status(job_id):
    job = jobs_dict[job_id]
    if not job:
        return "no such job {}".format(job_id)
    return job.status
