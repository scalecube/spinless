import json
import shlex
import threading
import uuid
from _datetime import datetime
from enum import Enum
from multiprocessing.context import Process
from subprocess import Popen, PIPE, STDOUT

from libs.log_api import *

jobs_dict = dict()


class JobState(Enum):
    CREATED = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
    CANCELLED = 5


class Status:

    def __init__(self, id):
        self.start = datetime.now()
        self.state = JobState.CREATED
        self.id = id
        self.end = ""
        self.elapsed = ""

    def update(self, state):
        self.state = state

    def finish(self, state):
        self.state = state
        self.end = datetime.now()
        self.elapsed = self.end - self.start

    def serialize(self):
        return json.dumps({
            "id": self.id,
            "state": self.state.name,
            "start": self.start.__str__(),
            "end": self.end.__str__() or "",
            "elapsed": self.elapsed.__str__() or ""
        })


class Job:
    def __init__(self, func, args, data):
        self.id = str(uuid.uuid1())
        self.owner = data.get("owner", "no_owner")
        self.repo = data.get("repo", "no_repo")
        self.status = Status(self.id)
        self.data = data
        self.proc = Process(target=func, args=(self, *args))
        self.proc.start()
        return

    def start(self):
        try:
            self.status.finish(JobState.RUNNING)

        except Exception as ex:
            self.status.finish(JobState.FAILED)
            self.__terminate()

    def stop(self):
        if self.__running():
            self.status.finish(JobState.CANCELLED)
        return self.__terminate()

    def get_log(self):
        def from_std(stream_to_generate):
            line = stream_to_generate.readline()
            while line:
                line_strip = line.strip()
                print("[LIVE] Streaming {} for job {}".format(line_strip, self.id))
                yield line_strip
                line = stream_to_generate.readline()

        def from_file(filename):
            if not os.path.isfile(filename):
                return "No log was found: {}".format(filename)
            with open(filename) as f:
                line = f.readline()
                while line:
                    strip = line.strip()
                    print("[LOG] Streaming {} for job {}".format(strip, self.id))
                    yield strip
                    line = f.readline()

        if self.__running():
            return from_std(self.proc.stdout)
        else:
            return from_file(self.logfile)

    def __running(self):
        return self.proc and self.proc.poll() is None

    def __terminate(self):
        if self.__running():
            self.proc.terminate()
            return True
        else:
            return False


def create_job(func, args, data):
    job = Job(func, args, data)
    jobs_dict[job.id] = job
    return job


def cancel_job(job_id):
    job = jobs_dict.get(job_id)
    if not job:
        return False
    return job.stop()


def get_job_log(job_id):
    job = jobs_dict.get(job_id)
    if not job:
        return "no such job {}".format(job_id)
    return job.get_log()


def get_job_status(job_id):
    job = jobs_dict.get(job_id)
    if not job:
        return "no such job {}".format(job_id)
    return job.status.serialize()
