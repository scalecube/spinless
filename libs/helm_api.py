from subprocess import Popen, PIPE


process = Popen(['echo', 'test'], stdout=PIPE, stderr=PIPE)
stdout, stderr = process.communicate()