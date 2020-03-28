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


def get_logger(owner, repo, id):
    PROJECT_FOLDER = os.path.dirname(sys.modules['__main__'].__file__)
    path = "{}/logs/{}/{}".format(PROJECT_FOLDER, owner, repo)
    create_dir(path)
    logger = logging.getLogger(id)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler("{}/{}.log".format(path, id), 'w', 'utf-8'))
    return logger


def tail_f(owner, repo, job_id, interval=1.0):

    try:
        PROJECT_FOLDER = os.path.dirname(sys.modules['__main__'].__file__)
        log_file = '{}/logs/{}/{}/{}.log'.format(PROJECT_FOLDER, owner, repo, job_id)
        file = open(log_file, 'r')
        for line in tailer.tail(file, 1000):
            if '"status": "EOF"' in line:
                break
            else:
                yield line

    except IOError:
        yield ''


def status(logger, id, status, message):
    data = {
        "id": id,
        "status": status,
        "timestamp": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        "message": message,
    }
    logger.info(json.dumps(data))
    pass


class JobLogger:

    def __init__(self, owner, repo, id):
        self.owner = owner
        self.repo = repo
        self.id = id
        self.logger = get_logger(owner, repo, id)
        self.emit = self.log

        return

    def info(self, message):
        self.logger.info('{}{}'.format(message, '\n'))
        pass

    def log(self, event_status, message):
        status(self.logger, self.id, event_status, message)
        self.logger.handlers[0].flush()
        pass

    def handlers(self):
        return self.logger.handlers.__len__() != 0

    def end(self):
        self.emit("EOF", '')
