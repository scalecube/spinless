import os
import time
import logging


class Logs:
    def __init__(self):
        return

    def get_logger(self, owner, repo, id):
        path = "/logs/{}/{}".format(owner, repo)
        self.create_dir(path)
        fh = logging.FileHandler("{}/{}.log".format(path, id))
        fh.setLevel(logging.DEBUG)

        logger = logging.getLogger(id)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(fh)
        return logger

    def create_dir(self, path):
        try:
            os.makedirs(path)
        except OSError:
            print("Creation of the directory %s failed" % path)
        else:
            print("Successfully created the directory %s" % path)

    def tail_f(self, path, interval=1.0):
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
