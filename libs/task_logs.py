import os
import time
import logging
import uuid
import json

from flask import jsonify


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
    fh = logging.FileHandler("{}/{}.log".format(path, id))
    fh.setLevel(logging.DEBUG)

    logger = logging.getLogger(id)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger


def tail_f(path, interval=1.0):
    file = open('logs/{}'.format(path))
    while True:
        where = file.tell()
        line = file.readline()
        if not line:
            time.sleep(interval)
            file.seek(where)
        elif line == 'EOF':
            break
        else:
            yield line
    pass


def status(task_log, data, id, status, message):
    data["id"] = id
    data["status"] = status
    data["timestamp"] = status
    data["message"] = message
    task_log.info(json.dumps(data))
    pass


class JobContext:

    def __init__(self, data):
        self.id = str(uuid.uuid1())
        self.data = data
        self.task_log = get_logger(data.get("owner"), data.get("repo"), self.id)
        return

    def update_status(self, event_status, message):
        status(self.task_log, self.data, self.id, event_status, message)
        pass

    def end(self):
        self.task_log.info("EOF")
