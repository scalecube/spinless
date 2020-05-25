import json
import time
import uuid
from enum import Enum
from multiprocessing import Process, Value

import psutil

from common.log_api import JobLogger

jobs_dict = dict()


class JobState(Enum):
    CREATED = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
    CANCELLED = 5


class Status:
    """Job state. Shared between processes"""

    def __init__(self, job_id, name="Noname"):
        self.id = job_id
        self.name = name
        self.state = Value('b', JobState.CREATED.value)
        self.start = time.time()
        self.end = Value("d", 0.0)
        self.elapsed = Value("d", 0.0)

    def update(self, state_code):
        self.state.value = state_code

    def finish(self, state_code):
        self.state.value = state_code
        curr = time.time()
        self.end.value = curr
        self.elapsed.value = curr - self.start

    def not_done(self):
        """Whether job is started or running"""
        return self.state.value <= JobState.SUCCESS.value

    def serialize(self):
        return json.dumps({
            "job_id": self.id,
            "name": self.name,
            "state": JobState(self.state.value).name,
            "start": int(self.start),
            "end": int(self.end.value),
            "elapsed": int(self.elapsed.value)
        })


class Job:
    def __init__(self, func, args, data):
        self.job_id = str(uuid.uuid1())
        self.data = data
        self.logger = JobLogger(self.job_id)
        self.proc = Process(target=func, args=(self, args))
        self.status = Status(self.job_id)

    def emit(self, _status, message):
        if not self.logger.handlers():
            self.logger = JobLogger(self.job_id)
        self.logger.emit(_status, message)

    def complete_err(self, msg):
        self.emit("ERROR", msg)
        self.__upd_state(JobState.FAILED)

    def complete_succ(self, msg):
        self.emit("SUCCESS", msg)
        self.__upd_state(JobState.SUCCESS)

    def start(self):
        try:
            self.__upd_state(JobState.RUNNING)
            self.proc.start()
        except Exception as ex:
            self.__upd_state(JobState.FAILED)
            self.__terminate()
        return self

    def cancel(self):
        if self.__running():
            self.__upd_state(JobState.CANCELLED)
        return self.__terminate()

    def __upd_state(self, _state):
        # Job complete
        if _state.value > JobState.RUNNING.value:
            self.status.finish(_state.value)
            self.logger.write_eof()
        else:
            self.status.update(_state.value)

    def __running(self):
        return self.proc and self.proc.pid and psutil.pid_exists(self.proc.pid)

    def __terminate(self):
        if self.__running():
            self.proc.terminate()
            return True
        else:
            return False


def create_job(func, app_logger, data):
    job = Job(func, app_logger, data)
    jobs_dict[job.job_id] = job
    return job


def get_job(job_id):
    return jobs_dict.get(job_id)


def cancel_job(job_id):
    job = jobs_dict.get(job_id)
    if not job:
        return False
    return job.cancel()


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
