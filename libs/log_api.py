import errno
import json
import logging
import os
import time


def get_logfile(owner, repo, id):
    path = "logs/{}/{}/{}.log".format(owner, repo, id)
    return __create_dirs(path)


def __create_dirs(filename):
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                print("Creation of the directory %s failed" % filename)
                raise
    return filename

def status(task_log, data, id, status, message):
    data["id"] = id
    data["status"] = status
    data["timestamp"] = status
    data["message"] = message
    task_log.info(json.dumps(data))
    pass
