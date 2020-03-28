import os
import sys
import time
import logging
import json
from datetime import datetime
import tailer


def create_dir(path):
    try:
        os.makedirs(path)
    except OSError:
        print("Creation of the directory %s failed" % path)
    else:
        print("Successfully created the directory %s" % path)


def create_logger(owner, repo, id):
    prj_dir = os.path.dirname(sys.modules['__main__'].__file__)
    path = "{}/logs/{}/{}".format(prj_dir, owner, repo)
    create_dir(path)
    logger = logging.getLogger(id)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler("{}/{}.log".format(path, id), 'w', 'utf-8'))
    return logger


def tail_f(owner, repo, job_id):

    PROJECT_FOLDER = os.path.dirname(sys.modules['__main__'].__file__)
    log_file = '{}/logs/{}/{}/{}.log'.format(PROJECT_FOLDER, owner, repo, job_id)
    while not os.path.exists(log_file):
        time.sleep(1)

    with open(log_file, 'a+') as file:
        file.seek(0)
        for line in file.readlines():
            yield line + '\n'
            if '"status": "EOF"' in line:
                return

        for line in tailer.follow(file):
            yield line + '\n'
            if '"status": "EOF"' in line:
                break




def status(logger, id, status, message):
    data = {
        "id": id,
        "status": status,
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
        return

    def info(self, message):
        self.logger.info('{}{}'.format(message, '\n'))
        pass

    def emit(self, event_status, message):
        status(self.logger, self.id, event_status, message)
        pass

    def handlers(self):
        return self.logger.handlers.__len__() != 0

    def write_eof(self):
        self.emit("EOF", '')
