import getpass
import json
import platform
import signal
import subprocess
import sys
import time
import os
import tempfile
import logging
import shutil
import re

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait


try:
    with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
        o = json.load(f)
except:
    print('''Failed to load config.json from the same directory as the execution server.

Example config.json:
{
  "cloudshell_server_address" : "192.168.2.108",
  "cloudshell_port": 8029,                                           // optional
  "cloudshell_snq_port": 9000,                                       // optional
  "cloudshell_username" : "admin",                                   // optional, default 'admin'

  "cloudshell_password" : "myadminpassword",
  // or
  "cloudshell_password" : "<ASK_AT_STARTUP>",                        // prompt for password at startup

  "cloudshell_domain" : "Global",                                    // optional, default 'Global'

  "cloudshell_execution_server_name" : "MyCES1",
  "cloudshell_execution_server_description" : "Robot CES in Python", // optional
  "cloudshell_execution_server_type" : "Robot",
  "cloudshell_execution_server_capacity" : "5",      // optional, default 5

  "log_directory": "/var/log",                       // . or full path - optional, default /var/log
  "log_level": "INFO",                               // CRITICAL|ERROR|WARNING|INFO|DEBUG - optional, default INFO
  "log_filename": "MyCES1.log",                      // optional, default <cloudshell_execution_server_name>.log

  "git_repo_url": "https://myuser:<ASK_AT_STARTUP>@github.com/myuser/myproj"  // prompt for password at startup
  // or
  "git_repo_url": "https://myuser@github.com/myuser/myproj"                   // prompt for passsword at startup
  // or
  "git_repo_url": "https://github.com/myuser/myproj"                          // clone without credentials

}

    ''')
    sys.exit(1)
server_description = o.get('cloudshell_execution_server_description', '')
server_capacity = int(o.get('cloudshell_execution_server_capacity', 5))
server_name = o.get('cloudshell_execution_server_name')
server_type = o.get('cloudshell_execution_server_type')
cloudshell_server_address = o.get('cloudshell_server_address')
cloudshell_snq_port = int(o.get('cloudshell_snq_port', 9000))
cloudshell_port = int(o.get('cloudshell_port', 8029))
cloudshell_username = o.get('cloudshell_username', 'admin')
cloudshell_password = o.get('cloudshell_password')
cloudshell_domain = o.get('cloudshell_domain', 'Global')
git_repo_url = o.get('git_repo_url')
log_directory = o.get('log_directory', '/var/log')
log_level = o.get('log_level', 'WARNING')
log_filename = o.get('log_filename', server_name + '.log')

errors = []
if not cloudshell_server_address:
    errors.append('cloudshell_server_address must be specified')
if not server_name:
    errors.append('server_name must be specified')
if not server_type:
    errors.append('server_type must be specified. The type must be registered in CloudShell portal under JOB SCHEDULING>Execution Server Types.')
if errors:
    raise Exception('Fix the following in config.json:\n' + '\n'.join(errors))

if not cloudshell_password or cloudshell_password == '<ASK_AT_STARTUP>':
    cloudshell_password = getpass.getpass('Enter password for CloudShell user %s: ' % cloudshell_username)

if '<ASK_AT_STARTUP>' in git_repo_url or ('@' in git_repo_url and ':' not in git_repo_url.replace('://', '')):
    s = getpass.getpass('Enter password for repo URL %s: ' % git_repo_url)
    s = s.replace('@', '%40')
    if '<ASK_AT_STARTUP>' in git_repo_url:
        git_repo_url = git_repo_url.replace('<ASK_AT_STARTUP>', s)
    else:
        git_repo_url = git_repo_url.replace('@', ':%s@' % s)


class ProcessRunner():
    def __init__(self, logger):
        self._logger = logger
        self._current_processes = {}
        self._stopping_processes = []
        self._running_on_windows = platform.system() == 'Windows'

    def execute_throwing(self, command, identifier, env=None):
        o, c = self.execute(command, identifier, env=env)
        if c:
            s = 'Error: %d: %s failed: %s' % (c, command, o)
            self._logger.error(s)
            raise Exception(s)

    def execute(self, command, identifier, env=None):
        env = env or {}
        pcommand = command
        pcommand = re.sub(r':[^@:]*@', ':(password hidden)@', pcommand)
        pcommand = re.sub(r"CLOUDSHELL_PASSWORD:[^']*", 'CLOUDSHELL_PASSWORD:(password hidden)', pcommand)
        penv = dict(env)
        if 'CLOUDSHELL_PASSWORD' in penv:
            penv['CLOUDSHELL_PASSWORD'] = '(hidden)'

        self._logger.debug('Execution %s: Running %s with env %s' % (identifier, pcommand, penv))
        if self._running_on_windows:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False, env=env)
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, preexec_fn=os.setsid, env=env)
        self._current_processes[identifier] = process
        output = ''
        if sys.version_info.major == 3:
            for line in iter(process.stdout.readline, b''):
                self._logger.debug('Output line: %s' % line)
                line = line.decode('utf-8', 'replace')
                output += line
        else:
            for line in iter(process.stdout.readline, b''):
                self._logger.debug('Output line: %s' % line)
                output += line
        process.communicate()
        self._current_processes.pop(identifier, None)
        if identifier in self._stopping_processes:
            self._stopping_processes.remove(identifier)
            return None
        return output, process.returncode

    def stop(self, identifier):
        self._logger.info('Received stop command for %s' % identifier)
        process = self._current_processes.get(identifier)
        if process is not None:
            self._stopping_processes.append(identifier)
            if self._running_on_windows:
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGTERM)


class MyCustomExecutionServerCommandHandler(CustomExecutionServerCommandHandler):

    def __init__(self, logger):
        CustomExecutionServerCommandHandler.__init__(self)
        self._logger = logger
        self._process_runner = ProcessRunner(self._logger)

    def execute(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        tempdir = tempfile.mkdtemp()
        os.chdir(tempdir)

        rjo = json.loads(reservation_json)

        git_branch_or_tag_spec = None
        for v in rjo['TopologyInputs']:
            if v['Name'] == 'TestVersion':
                git_branch_or_tag_spec = v['Value']
        if git_branch_or_tag_spec == 'None':
            git_branch_or_tag_spec = None
        # MYBRANCHNAME or tags/MYTAGNAME

        self._process_runner.execute_throwing('git clone %s repo' % git_repo_url, execution_id+'_git1')

        os.chdir(tempdir + '/repo')

        if git_branch_or_tag_spec:
            self._process_runner.execute_throwing('git checkout %s' % git_branch_or_tag_spec, execution_id+'_git2')
        else:
            self._logger.info('TestVersion not specified - taking latest from default branch')

        t = 'robot'
        # t += ' --variable CLOUDSHELL_RESERVATION_ID:%s' % reservation_id
        # t += ' --variable CLOUDSHELL_SERVER_ADDRESS:%s' % cloudshell_server_address
        # t += ' --variable CLOUDSHELL_PORT:%d' % cloudshell_port
        # t += ' --variable CLOUDSHELL_USERNAME:%s' % cloudshell_username
        # t += " --variable 'CLOUDSHELL_PASSWORD:%s'" % cloudshell_password
        # t += ' --variable CLOUDSHELL_DOMAIN:%s' % cloudshell_domain
        if test_arguments and test_arguments != 'None':
            t += ' ' + test_arguments
        t += ' %s' % test_path

        output, robotretcode = self._process_runner.execute(t, execution_id, env={
            'CLOUDSHELL_RESERVATION_ID': reservation_id,
            'CLOUDSHELL_SERVER_ADDRESS': cloudshell_server_address,
            'CLOUDSHELL_SERVER_PORT': str(cloudshell_port),
            'CLOUDSHELL_USERNAME': cloudshell_username,
            'CLOUDSHELL_PASSWORD': cloudshell_password,
            'CLOUDSHELL_DOMAIN': cloudshell_domain,
        })

        now = time.strftime("%b-%d-%Y_%H.%M.%S")

        zipname = '%s_%s.zip' % (test_path, now)
        self._process_runner.execute_throwing('zip %s output.xml log.html report.html' % zipname, execution_id+'_zip')

        with open(zipname, 'rb') as f:
            zipdata = f.read()

        os.chdir('/')
        shutil.rmtree(tempdir)
        if robotretcode == 0:
            return PassedCommandResult(zipname, zipdata, 'application/zip')
        else:
            return FailedCommandResult(zipname, zipdata, 'application/zip')

    def stop(self, execution_id, logger):
        logger.info('stop %s\n' % execution_id)
        self._process_runner.stop(execution_id)

logger = logging.getLogger(server_name)
handler = logging.FileHandler('%s/%s' % (log_directory, log_filename))
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)
if log_level:
    logger.setLevel(logging.getLevelName(log_level.upper()))

server = CustomExecutionServer(server_name=server_name,
                               server_description=server_description,
                               server_type=server_type,
                               server_capacity=server_capacity,

                               command_handler=MyCustomExecutionServerCommandHandler(logger),

                               logger=logger,

                               cloudshell_host=cloudshell_server_address,
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
            s = '%s execution server %s started\nTo stop:\nkill -s SIGUSR1 %d' % (server_type, server_name, os.getpid())
            logger.info(s)
            print (s)

        def daemon_stop():
            logger.info("Stopping, please wait up to 2 minutes...")
            print ("Stopping, please wait up to 2 minutes...")
            server.stop()
            logger.info("Stopped")
            print ("Stopped")

        become_daemon_and_wait(daemon_start, daemon_stop, exit_signal=30)

