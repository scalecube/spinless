import json
import logging
import os
import sys
import time
import re

import tailer


def create_dir(path):
    try:
        os.makedirs(path)
    except OSError:
        print("Creation of the directory %s failed" % path)
    else:
        print("Successfully created the directory %s" % path)


def create_logger(owner, repo, job_id):
    prj_dir = os.path.dirname(sys.modules['__main__'].__file__)
    path = "{}/state/logs/{}/{}".format(prj_dir, owner, repo)
    create_dir(path)
    logger = logging.getLogger(job_id)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler("{}/{}.log".format(path, job_id), 'w', 'utf-8'))
    return logger


def tail_f(owner, repo, job_id):
    prj_dir = os.path.dirname(sys.modules['__main__'].__file__)
    log_file = '{}/state/logs/{}/{}/{}.log'.format(prj_dir, owner, repo, job_id)
    while not os.path.exists(log_file):
        time.sleep(1)

    with open(log_file, 'a+') as file:
        file.seek(0)
        for line in file.readlines():
            if '"status": "EOF"' in line:
                return
            yield line + '\n'

        for line in tailer.follow(file):
            yield line + '\n'
            if '"status": "EOF"' in line:
                break


def redacted(message):
    msg = re.sub(r"(dockerconfigjson).*(=|:)(.*)?\s*(>*)", "dockerconfigjson=[REDACTED]", message)
    msg = re.sub(r"(dockerjsontoken).*(=|:)(.*)?\s*(>*)", "dockerjsontoken=[REDACTED]", msg)
    return msg


def status(logger, job_id, _status, message):
    data = {
        "id": job_id,
        "status": _status,
        "timestamp": int(time.time() * 1000),
        "message": message,
    }
    logger.info(json.dumps(data))
    logger.handlers[0].flush()
    pass


class JobLogger:

    def __init__(self, owner, repo, id):
        self.owner = owner
        self.repo = repo
        self.id = id
        self.logger = create_logger(owner, repo, id)

    def info(self, message):
        self.logger.info('{}{}'.format(message, '\n'))

    def emit(self, event_status, message):
        status(self.logger, self.id, event_status, message)

    def handlers(self):
        return self.logger.handlers.__len__() != 0

    def write_eof(self):
        self.emit("EOF", '')
