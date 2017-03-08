import os
import time

import signal

def handler(signum, frame):
    print ("Stopping, please wait up to 2 minutes...")
sg = 30
signal.signal(sg, handler)

print os.getpid()
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        os.chdir('/')
        os.umask(0)
    else:
        os._exit(0)
else:
    os._exit(0)

