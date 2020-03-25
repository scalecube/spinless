import os
import shlex
import uuid
from subprocess import Popen, PIPE

stream_dict = dict()


def start_logging(cmd):
    stream_id = uuid.uuid1()
    try:
        with Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE) as process, open(str(stream_id) + '.log',
                                                                                'w') as logfile:
            # save stream to dict
            s_out = process.stdout
            stream_dict[str(stream_id)] = s_out
            for line in iter(s_out.readline, b''):
                logfile.write(line.decode("utf-8"))
    except Exception as exc:
        return "Failed to execute: {}".format(exc.with_traceback())
    return stream_id


def get_log(stream_id):
    def from_std(stream_to_generate):
        line = stream_to_generate.readline()
        while line:
            yield line.strip()
            line = stream_to_generate.readline()

    def from_file(filename):
        with open(filename) as f:
            line = f.readline()
            while line:
                yield line.strip()
                line = f.readline()

        # for line in stream_to_generate.readline():
        #     yield line.decode("utf-8")

    # try opened stream first (job in progress)
    log_out = stream_dict.get(stream_id)
    if log_out:
        return from_std(log_out)
    # if not read from logfile
    log_name = str(stream_id) + ".log"
    if os.path.isfile(log_name):
        return from_file(log_name)

    else:
        return "no such job {}".format(stream_id)
    # del stream_dict[stream_id]