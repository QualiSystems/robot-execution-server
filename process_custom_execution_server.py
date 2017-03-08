import json
import os
import platform
import signal
import subprocess
import sys
import time

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult

import os


class ProcessRunner():
    def __init__(self):
        self._current_processes = {}
        self._stopping_processes = []
        self._running_on_windows = platform.system() == 'Windows'

    def execute(self, command, identifier):
        if self._running_on_windows:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid)
        self._current_processes[identifier] = process
        output = ''
        if sys.version_info.major == 3:
            for line in iter(process.stdout.readline, b''):
                print('Output line: %s' % line)
                line = line.decode('utf-8', 'replace')
                output += line
        else:
            for line in iter(process.stdout.readline, b''):
                output += line
        process.communicate()
        self._current_processes.pop(identifier, None)
        if identifier in self._stopping_processes:
            self._stopping_processes.remove(identifier)
            return None
        return output, process.returncode

    def stop(self, identifier):
        process = self._current_processes.get(identifier)
        if process is not None:
            self._stopping_processes.append(identifier)
            if self._running_on_windows:
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGTERM)


class MyCustomExecutionServerCommandHandler(CustomExecutionServerCommandHandler):

    def __init__(self):
        CustomExecutionServerCommandHandler.__init__(self)
        self._process_runner = ProcessRunner()

    def execute(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        t = test_path
        if test_arguments:
            t += ' ' + test_arguments
        output, retcode = self._process_runner.execute(t, execution_id)
        now = time.strftime("%b-%d-%Y_%H.%M.%S")
        print('execute result: %d: %s\n' % (retcode, output))
        if retcode != 0:
            return FailedCommandResult('%s-status%d.txt' % (now, retcode), output)
        else:
            return PassedCommandResult('%s.txt' % now, output)

    def stop(self, execution_id, logger):
        logger.info('stop %s\n' % execution_id)
        self._process_runner.stop(execution_id)


class Logger:
    def warn(self, s):
        print(s + '\n')
    def debug(self, s):
        print(s + '\n')
        pass
    def info(self, s):
        print(s + '\n')
    def error(self, s):
        print(s + '\n')


with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    o = json.load(f)

# o = json.loads('''{
# "host" : "http://localhost:9000",
# "username" : "admin",
# "password" : "admin",
# "domain" : "Global",
# "name" : "MyCES1",
# "description" : "Reference implementation CES in Python",
# "type" : "Python",
# "capacity" : "5"
# }
# ''')

if __name__ == '__main__':
    logger = Logger()
    servername = o['name']
    servertype = o['type']
    server = CustomExecutionServer(server_name=servername,
                                   server_description=o['description'],
                                   server_type=servertype,
                                   server_capacity=int(o['capacity']),

                                   command_handler=MyCustomExecutionServerCommandHandler(),

                                   logger=logger,

                                   cloudshell_host=o['host'].split('/')[-1].split(':')[0],
                                   cloudshell_port=int(o['host'].split('/')[-1].split(':')[1]),
                                   cloudshell_username=o['username'],
                                   cloudshell_password=o['password'],
                                   cloudshell_domain=o['domain'],

                                   auto_register=False,
                                   auto_start=False)


    if len(sys.argv) > 1:
        if sys.argv[1] == 'register':
            server.register()
            print('Successfully registered.')
            sys.exit(0)
        elif sys.argv[1] == 'update':
            server.update()
            print('Successfully updated.')
            sys.exit(0)
        else:
            print('Python custom execution server can take one of two optional arguments:')
            print('register - register the execution server with details from config.json')
            print('update - update the details of the execution server to those in config.json')
            sys.exit(1)
    else:
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except:
            pass
        if os.fork() == 0:
            os.setsid()
            if os.fork() == 0:
                os.chdir('/')
                os.umask(0)
            else:
                os._exit(0)
        else:
            os._exit(0)

        def handler(signum, frame):
            print ("Stopping, please wait up to 2 minutes...")
            server.stop()
            print ("Stopped")

        sg = 30
        signal.signal(sg, handler)
        server.start()
        print ('%s execution server %s started' % (servertype, servername))
        print ('kill -s %d %d to stop. Shutdown takes up to 2 minutes.' % (sg, os.getpid()))

            # if sys.version_info.major == 2:
        #     raw_input()
        # else:
        #     input()

