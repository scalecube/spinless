import os
import time
import logging
import json
from datetime import datetime


def create_dir(path):
    try:
        os.makedirs(path)
    except OSError:
        print("Creation of the directory %s failed" % path)
    else:
        print("Successfully created the directory %s" % path)


def get_logger(owner, repo, id):
    path = "logs/{}/{}".format(owner, repo)
    create_dir(path)
    logger = logging.getLogger(id)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.FileHandler("{}/{}.log".format(path, id), 'w', 'utf-8'))
    return logger


def tail_f(path, interval=1.0):
    file = open('logs/{}'.format(path))
    while True:
        where = file.tell()
        line = file.readline()
        if not line:
            time.sleep(interval)
            file.seek(where)
        elif line.startswith('EOF'):
            file.close()
            break
        else:
            yield line
    pass


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
        self.logger.info(message)
        pass

    def log(self, event_status, message):
        status(self.logger, self.id, event_status, message)
        pass

    def end(self):
        self.logger.info("EOF")
