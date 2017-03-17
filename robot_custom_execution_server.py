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
import traceback
from logging.handlers import RotatingFileHandler

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult, ErrorCommandResult, StoppedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait


def string23(b):
    if sys.version_info.major == 3:
        if isinstance(b, bytes):
            return b.decode('utf-8', 'replace')
    return b or ''


def input23(msg):
    if sys.version_info.major == 3:
        return input(msg)
    else:
        return raw_input(msg)

jsonexample = '''Example config.json:
{
  "cloudshell_server_address" : "192.168.2.108",
  "cloudshell_port": 8029,
  "cloudshell_snq_port": 9000,

  "cloudshell_username" : "admin",
  // or
  "cloudshell_username" : "<PROMPT>",

  "cloudshell_password" : "myadminpassword",
  // or
  "cloudshell_password" : "<PROMPT>",

  "cloudshell_domain" : "Global",

  "cloudshell_execution_server_name" : "MyCES1",
  "cloudshell_execution_server_description" : "Robot CES in Python",
  "cloudshell_execution_server_type" : "Robot",
  "cloudshell_execution_server_capacity" : "5",

  "log_directory": "/var/log",
  "log_level": "INFO",
  // CRITICAL | ERROR | WARNING | INFO | DEBUG
  "log_filename": "<EXECUTION_SERVER_NAME>.log",

  "scratch_directory": "/tmp",

  "git_repo_url": "https://<PROMPT_GIT_USERNAME>:<PROMPT_GIT_PASSWORD>@github.com/myuser/myproj",
  "git_default_checkout_version": "master"

}
Note: Remove all // comments before using
'''
configfile = os.path.join(os.path.dirname(__file__), 'config.json')

if len(sys.argv) > 1:
    usage = '''CloudShell Robot execution server automatic self-registration and launch
Usage: 
    python %s                                      # run with %s
    python %s --config <path to JSON config file>  # run with JSON config file from custom location
    python %s -c <path to JSON config file>        # run with JSON config file from custom location

%s
The server will run in the background. Send SIGTERM to shut it down.
''' % (sys.argv[0], configfile, sys.argv[0], sys.argv[0], jsonexample)
    for i in range(1, len(sys.argv)):
        if sys.argv[i] in ['--help', '-h', '-help', '/?', '/help', '-?']:
            print(usage)
            sys.exit(1)
        if sys.argv[i] in ['--config', '-c']:
            if i+1 < len(sys.argv):
                configfile = sys.argv[i+1]
            else:
                print(usage)
                sys.exit(1)

try:
    with open(configfile) as f:
        o = json.load(f)
except:
    print('''%s

Failed to load JSON config file "%s".

%s

    ''' % (traceback.format_exc(), configfile, jsonexample))
    sys.exit(1)

cloudshell_server_address = o.get('cloudshell_server_address')
server_name = o.get('cloudshell_execution_server_name')
server_type = o.get('cloudshell_execution_server_type')

errors = []
if not cloudshell_server_address:
    errors.append('cloudshell_server_address must be specified')
if not server_name:
    errors.append('server_name must be specified')
if not server_type:
    errors.append('server_type must be specified. The type must be registered in CloudShell portal under JOB SCHEDULING>Execution Server Types.')
if errors:
    raise Exception('Fix the following in config.json:\n' + '\n'.join(errors))

cloudshell_username = o.get('cloudshell_username', '<PROMPT>')
cloudshell_password = o.get('cloudshell_password', '<PROMPT>')

if '<PROMPT>' in cloudshell_username:
    cloudshell_username = cloudshell_username.replace('<PROMPT>', input23('CloudShell username: '))
if '<PROMPT>' in cloudshell_password:
    cloudshell_password = cloudshell_password.replace('<PROMPT>', getpass.getpass('CloudShell password: '))

git_repo_url = o.get('git_repo_url')

if '<PROMPT_GIT_USERNAME>' in git_repo_url:
    git_repo_url = git_repo_url.replace('<PROMPT_GIT_USERNAME>', input23('Git username: '))
if '<PROMPT_GIT_PASSWORD>' in git_repo_url:
    git_repo_url = git_repo_url.replace('<PROMPT_GIT_PASSWORD>', getpass.getpass('Git password: ').replace('@', '%40'))

for k in list(o.keys()):
    v = str(o[k])
    if '<EXECUTION_SERVER_NAME>' in v:
        o[k] = o[k].replace('<EXECUTION_SERVER_NAME>', server_name)

server_description = o.get('cloudshell_execution_server_description', '')
server_capacity = int(o.get('cloudshell_execution_server_capacity', 5))
cloudshell_snq_port = int(o.get('cloudshell_snq_port', 9000))
cloudshell_port = int(o.get('cloudshell_port', 8029))
cloudshell_domain = o.get('cloudshell_domain', 'Global')
log_directory = o.get('log_directory', '/var/log')
log_level = o.get('log_level', 'INFO')
log_filename = o.get('log_filename', server_name + '.log')
scratch_dir = o.get('scratch_dir', '/tmp')
default_checkout_version = o.get('git_default_checkout_version', '')


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
        return o, c

    def execute(self, command, identifier, env=None):
        env = env or {}
        if True:
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
        for line in iter(process.stdout.readline, b''):
            line = string23(line)
            self._logger.debug('Output line: %s' % line)
            output += line
        process.communicate()
        self._current_processes.pop(identifier, None)
        if identifier in self._stopping_processes:
            self._stopping_processes.remove(identifier)
            return None, -6000
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

    def execute_command(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        try:
            tempdir = tempfile.mkdtemp(dir=scratch_dir)

            resinfo = json.loads(reservation_json) if reservation_json and reservation_json != 'None' else None

            git_branch_or_tag_spec = None

            if test_arguments:
                versionre = r'TestVersion=([-_./0-9a-zA-Z]*)'
                m = re.search(versionre, test_arguments)
                if m:
                    git_branch_or_tag_spec = m.groups()[0]
                    test_arguments = re.sub(versionre, '', test_arguments).strip()

            if not git_branch_or_tag_spec:
                if resinfo:
                    for v in resinfo['TopologyInputs']:
                        if v['Name'] == 'TestVersion':
                            git_branch_or_tag_spec = v['Value']
            if git_branch_or_tag_spec == 'None':
                git_branch_or_tag_spec = None


            if not git_branch_or_tag_spec:
                git_branch_or_tag_spec = default_checkout_version
            # MYBRANCHNAME or tags/MYTAGNAME

            self._process_runner.execute_throwing('git clone %s %s' % (git_repo_url, tempdir), execution_id+'_git1')

            if git_branch_or_tag_spec:
                self._process_runner.execute_throwing('git reset --hard', execution_id+'_git2', env={
                    'GIT_DIR': '%s/.git' % tempdir
                })
                self._process_runner.execute_throwing('git checkout %s' % git_branch_or_tag_spec, execution_id+'_git2', env={
                    'GIT_DIR': '%s/.git' % tempdir
                })
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
            t += ' -d %s %s/%s' % (tempdir, tempdir, test_path)

            try:
                output, robotretcode = self._process_runner.execute(t, execution_id, env={
                    'CLOUDSHELL_RESERVATION_ID': reservation_id or 'None',
                    'CLOUDSHELL_SERVER_ADDRESS': cloudshell_server_address or 'None',
                    'CLOUDSHELL_SERVER_PORT': str(cloudshell_port) or 'None',
                    'CLOUDSHELL_USERNAME': cloudshell_username or 'None',
                    'CLOUDSHELL_PASSWORD': cloudshell_password or 'None',
                    'CLOUDSHELL_DOMAIN': cloudshell_domain or 'None',
                    'CLOUDSHELL_RESERVATION_INFO': reservation_json or 'None',
                })
            except Exception as uue:
                robotretcode = -5000
                output = 'Robot crashed: %s: %s' % (uue, traceback.format_exc())

            if robotretcode == -6000:
                return StoppedCommandResult()

            self._logger.debug('Result of %s: %d: %s' % (t, robotretcode, string23(output)))

            if 'Data source does not exist' in output:
                return ErrorCommandResult('Robot failure', 'Test file %s/%s missing (at version %s). Original error: %s' % (tempdir, test_path, git_branch_or_tag_spec or '[repo default branch]', output))

            now = time.strftime("%b-%d-%Y_%H.%M.%S")

            zipname = '%s_%s.zip' % (test_path, now)
            try:
                zipoutput, _ = self._process_runner.execute_throwing('zip -j %s/%s %s/output.xml %s/log.html %s/report.html' % (tempdir, zipname, tempdir, tempdir, tempdir), execution_id+'_zip')
            except:
                return ErrorCommandResult('Robot failure', 'Robot did not complete: %s' % string23(output))

            with open('%s/%s' % (tempdir, zipname), 'rb') as f:
                zipdata = f.read()

            shutil.rmtree(tempdir)

            if robotretcode == 0:
                return PassedCommandResult(zipname, zipdata, 'application/zip')
            else:
                return FailedCommandResult(zipname, zipdata, 'application/zip')
        except Exception as ue:
            self._logger.error(str(ue) + ': ' + traceback.format_exc())
            raise ue

    def stop_command(self, execution_id, logger):
        logger.info('stop %s\n' % execution_id)
        self._process_runner.stop(execution_id)

log_pathname = '%s/%s' % (log_directory, log_filename)
logger = logging.getLogger(server_name)
handler = RotatingFileHandler(log_pathname, maxBytes=100000, backupCount=100)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)
if log_level:
    logger.setLevel(logging.getLevelName(log_level.upper()))

print('\nLogging to %s\n' % log_pathname)

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

                               auto_register=True,
                               auto_start=False)


def daemon_start():
    server.start()
    s = '\n\n%s execution server %s started\nTo stop %s:\nkill %d\n\nIt is safe to close this terminal.\n' % (server_type, server_name, server_name, os.getpid())
    logger.info(s)
    print (s)


def daemon_stop():
    msgstopping = "Stopping execution server %s, please wait up to 2 minutes..." % server_name
    msgstopped = "Execution server %s finished shutting down" % server_name
    logger.info(msgstopping)
    print (msgstopping)
    try:
        subprocess.call(['wall', msgstopping])
    except:
        pass
    server.stop()
    logger.info(msgstopped)
    print (msgstopped)
    try:
        subprocess.call(['wall', msgstopped])
    except:
        pass

become_daemon_and_wait(daemon_start, daemon_stop)
