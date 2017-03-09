import json
import platform
import signal
import subprocess
import sys
import time
import os
import tempfile

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait


with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    o = json.load(f)

server_description = o['cloudshell_execution_server_description']
server_capacity = int(o['cloudshell_execution_server_capacity'])
server_name = o['cloudshell_execution_server_name']
server_type = o['cloudshell_execution_server_type']
cloudshell_host = o['cloudshell_host']
cloudshell_snq_port = int(o['cloudshell_snq_port'])
cloudshell_port = int(o['cloudshell_port'])
cloudshell_username = o['cloudshell_admin_username']
cloudshell_password = o['cloudshell_admin_password']
cloudshell_domain = o['cloudshell_domain']
git_repo_url = o['git_repo_url']

if cloudshell_password == '<ASK_AT_STARTUP>':
    cloudshell_password = input('Enter password for CloudShell user %s: ' % cloudshell_username)

if '<ASK_AT_STARTUP>' in git_repo_url:
    s = input('Enter password for URL %s: ' % git_repo_url)
    git_repo_url = git_repo_url.replace('<ASK_AT_STARTUP>', s)


class ProcessRunner():
    def __init__(self):
        self._current_processes = {}
        self._stopping_processes = []
        self._running_on_windows = platform.system() == 'Windows'

    def execute_throwing(self, command, identifier):
        o, c = self.execute(command, identifier)
        if c:
            raise Exception('Error: %d: %s failed: %s' % (c, command, o))

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
        # logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        wd = tempfile.mkdtemp()
        os.chdir(wd)

        rjo = json.loads(reservation_json)
        # {
        #     "Id":"651f1b1c-fa7c-4199-8d96-3fff612eaefe",
        #     "Name":"j1",
        #     "Owner":{"UserName":"admin","Email":null,"DisplayName":"admin","Groups":["System Administrators","Everyone"]},
        #     "PermittedUsers":[{"UserName":"admin","Email":null,"DisplayName":"admin","Groups":["System Administrators","Everyone"]}],
        #     "StartTime":"2017-03-07T23:12:00",
        #     "EndTime":"2017-03-07T23:33:00",
        #     "Domain":"Global",
        #     "Topology":"Root\\ROBOT ENV",
        #     "TopologyInputs":[
        #     {"Name":"TestVersion","Type":0,"AbstractId":"00000000-0000-0000-0000-000000000000","AbstractAlias":"","GlobalName":null,"Value":"BunnyDiana/editmehtml-edited-online-with-bitbucket-1413226554474","Description":null,"ValueType":1,"PossibleValues":[],"MaxQuantity":0}
        #     ],
        #     "Resources":[],
        #     "Services":[],
        #     "Apps":null,
        #     "Routes":[],
        #     "Connectors":[],
        #     "ReservationStatus":1,
        #     "IsBuildType":false
        # }

        git_branch_or_tag_spec = ([v['Value'] for v in rjo['TopologyInputs'] if v['Name'] == 'TestVersion'] + ['Error-TestVersion-Missing'])[0]
        # MYBRANCHNAME or tags/MYTAGNAME

        self._process_runner.execute_throwing('git clone %s repo' % git_repo_url, execution_id+'_git1')

        os.chdir(wd + '/repo')

        self._process_runner.execute_throwing('git checkout %s' % git_branch_or_tag_spec, execution_id+'_git2')

        t = 'robot %s' % test_path
        t += ' --variable CLOUDSHELL_RESERVATION_ID:%s' % reservation_id
        t += ' --variable CLOUDSHELL_HOST:%s' % cloudshell_host
        t += ' --variable CLOUDSHELL_PORT:%d' % cloudshell_port
        t += ' --variable CLOUDSHELL_USERNAME:%s' % cloudshell_username
        t += ' --variable CLOUDSHELL_PASSWORD:%s' % cloudshell_password
        t += ' --variable CLOUDSHELL_DOMAIN:%s' % cloudshell_domain
        if test_arguments and test_arguments != 'None':
            t += ' ' + test_arguments

        output, robotretcode = self._process_runner.execute(t, execution_id)

        now = time.strftime("%b-%d-%Y_%H.%M.%S")
        # print('execute result: %d: %s\n' % (retcode, output))

        zipname = '%s_%s.zip' % (test_path, now)
        self._process_runner.execute_throwing('zip %s output.xml log.html report.html' % zipname, execution_id+'_zip')

        with open(zipname, 'rb') as f:
            zipdata = f.read()

        if robotretcode == 0:
            return PassedCommandResult(zipname, zipdata)
        else:
            return FailedCommandResult(zipname, zipdata)

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

logger = Logger()
server = CustomExecutionServer(server_name=server_name,
                               server_description=server_description,
                               server_type=server_type,
                               server_capacity=server_capacity,

                               command_handler=MyCustomExecutionServerCommandHandler(),

                               logger=logger,

                               cloudshell_host=cloudshell_host,
                               cloudshell_port=cloudshell_snq_port,
                               cloudshell_username=cloudshell_username,
                               cloudshell_password=cloudshell_password,
                               cloudshell_domain=cloudshell_domain,

                               auto_register=False,
                               auto_start=False)

if __name__ == '__main__':
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
        def daemon_start():
            server.start()
            print ('%s execution server %s started' % (server_type, server_name))
            print ('kill -s 30 %d to stop. Shutdown takes up to 2 minutes.' % os.getpid())

        def daemon_stop():
            print ("Stopping, please wait up to 2 minutes...")
            server.stop()
            print ("Stopped")

        become_daemon_and_wait(daemon_start, daemon_stop, exit_signal=30)

