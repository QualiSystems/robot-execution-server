import sys
import os
import getpass
import json
import subprocess
import time
import logging
import shutil
import re
import traceback
from logging.handlers import RotatingFileHandler

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cloudshell-custom-execution-server'))

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer, CustomExecutionServerCommandHandler, PassedCommandResult, \
    FailedCommandResult, ErrorCommandResult, StoppedCommandResult

from cloudshell.custom_execution_server.daemon import become_daemon_and_wait
from cloudshell.custom_execution_server.process_manager import ProcessRunner


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

jsonexample = r'''Example config.json:
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
  "cloudshell_execution_server_capacity" : 5,

  "log_directory": "/var/log",
  "log_level": "INFO",
  // CRITICAL | ERROR | WARNING | INFO | DEBUG
  "log_filename": "<EXECUTION_SERVER_NAME>.log",

  "unique_output_directory": "/mnt/share1/robot_output/%R_%U/%N_%V_%T",
  "delete_output_after_run": false,
  "archive_output_xml_to": "/mnt/share1/robot_logs/%R_%U/%N_%V_%T.xml",
  "postprocessing_command": "/mnt/share1/scripts/postprocess.sh /mnt/share1/robot_logs/%R_%U/%N_%V_%T.xml",


  "git_repo_url": "https://<PROMPT_GIT_USERNAME>:<PROMPT_GIT_PASSWORD>@github.com/myuser/myproj",
  "git_default_checkout_version": "master",
  
  "robot_environment_json": "{\"PYTHONPATH\": \"/home/jrobot/app/executions/libs/\"}"

}
// %R = reservation id
// %V = version (tag, branch, or commit id)
// %N = test name
// %U = CloudShell user who ran the test
// %T = timestamp YYYY-MM-DD_hh.mm.ss

Note: Remove all // comments before using
'''
configfile = os.path.join(os.path.dirname(__file__), 'config.json')

usage = '''CloudShell Robot execution server automatic self-registration and launch
Usage: 
    python %s                                      # run with %s
    python %s --config <path to JSON config file>  # run with JSON config file from custom location
    python %s -c <path to JSON config file>        # run with JSON config file from custom location

%s
The server will run in the background. Send SIGTERM to shut it down.
''' % (sys.argv[0], configfile, sys.argv[0], sys.argv[0], jsonexample)
if len(sys.argv) > 1:
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
%s

Failed to load JSON config file "%s".
''' % (traceback.format_exc(), usage, configfile))
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
unique_output_directory = o.get('unique_output_directory', '/tmp')
delete_output = o.get('delete_output_after_run', False)
archive_output_xml_to = o.get('archive_output_xml_to', '')
postprocessing_command = o.get('postprocessing_command', '')
default_checkout_version = o.get('git_default_checkout_version', '')
env_json = o.get('robot_environment_json', '')

if env_json:
    env_json = json.loads(env_json)
else:
    env_json = None


class MyCustomExecutionServerCommandHandler(CustomExecutionServerCommandHandler):

    def __init__(self, logger):
        CustomExecutionServerCommandHandler.__init__(self)
        self._logger = logger
        self._process_runner = ProcessRunner(self._logger)

    def execute_command(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        if '..' in test_path:
            raise Exception('Double dot not allowed in test path')
        try:
            now = time.strftime("%Y-%m-%d_%H.%M.%S")
            resinfo = json.loads(reservation_json) if reservation_json and reservation_json != 'None' else None
            git_branch_or_tag_spec = ''

            if test_arguments:
                versionre = r'TestVersion=([-@%_/.,0-9a-zA-Z]*)'
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
                git_branch_or_tag_spec = ''

            if not git_branch_or_tag_spec:
                git_branch_or_tag_spec = default_checkout_version

            if not git_branch_or_tag_spec:
                git_branch_or_tag_spec = 'DEFAULT'

            if git_branch_or_tag_spec:
                if git_branch_or_tag_spec.startswith('.') or \
                                '/.' in git_branch_or_tag_spec or \
                                '..' in git_branch_or_tag_spec or \
                        git_branch_or_tag_spec.endswith('/') or \
                        git_branch_or_tag_spec.endswith('.lock') or \
                                '~' in git_branch_or_tag_spec or \
                                '^' in git_branch_or_tag_spec or \
                                ':' in git_branch_or_tag_spec or \
                                '\\' in git_branch_or_tag_spec or \
                                ' ' in git_branch_or_tag_spec or \
                                '\t' in git_branch_or_tag_spec or \
                                '\r' in git_branch_or_tag_spec or \
                                '\n' in git_branch_or_tag_spec:
                    raise Exception('Illegal branch or tag name %s' % git_branch_or_tag_spec)

            def cdrip(fn):
                fn = fn.replace('%T', now)
                if reservation_id:
                    fn = fn.replace('%R', reservation_id)
                else:
                    fn = fn.replace('%R', 'NO_RESERVATION')
                if test_path:
                    fn = fn.replace('%N', test_path.replace('/', '__').replace(' ', '_'))
                if git_branch_or_tag_spec:
                    fn = fn.replace('%V', git_branch_or_tag_spec.replace('/', '__').replace(' ', '_'))
                if username:
                    fn = fn.replace('%U', username)
                return fn

            outdir = cdrip(unique_output_directory)
            os.makedirs(outdir, exist_ok=True)

            # MYBRANCHNAME or tags/MYTAGNAME

            # if git_branch_or_tag_spec:
            #     minusb = '-b %s' % git_branch_or_tag_spec
            # else:
            #     minusb = ''
            #     self._logger.info('TestVersion not specified - taking latest from default branch')
            #
            # self._process_runner.execute_throwing('git clone %s %s %s' % (minusb, git_repo_url, outdir), execution_id+'_git1')
            self._process_runner.execute_throwing(['git', 'clone', git_repo_url, outdir], execution_id+'_git1')

            if git_branch_or_tag_spec != 'DEFAULT':
                # self._process_runner.execute_throwing('git reset --hard', execution_id+'_git2', env={
                #     'GIT_DIR': '%s/.git' % outdir
                # })
                self._process_runner.execute_throwing(['git', 'checkout', git_branch_or_tag_spec], execution_id+'_git3', directory=outdir)
                # env={
                #     'GIT_DIR': '%s/.git' % outdir
                # })
            else:
                self._logger.info('TestVersion not specified - taking latest from default branch')

            tt = ['robot']
            # t += ' --variable CLOUDSHELL_RESERVATION_ID:%s' % reservation_id
            # t += ' --variable CLOUDSHELL_SERVER_ADDRESS:%s' % cloudshell_server_address
            # t += ' --variable CLOUDSHELL_PORT:%d' % cloudshell_port
            # t += ' --variable CLOUDSHELL_USERNAME:%s' % cloudshell_username
            # t += " --variable 'CLOUDSHELL_PASSWORD:%s'" % cloudshell_password
            # t += ' --variable CLOUDSHELL_DOMAIN:%s' % cloudshell_domain
            if test_arguments and test_arguments != 'None':
                tt += test_arguments.split(' ')
            # tt.append('-d')
            # tt.append(outdir)
            # tt += test_path.split(' ')
            tt.append(test_path)

            try:
                env = {
                    'CLOUDSHELL_RESERVATION_ID': reservation_id or 'None',
                    'CLOUDSHELL_SERVER_ADDRESS': cloudshell_server_address or 'None',
                    'CLOUDSHELL_SERVER_PORT': str(cloudshell_port) or 'None',
                    'CLOUDSHELL_USERNAME': cloudshell_username or 'None',
                    'CLOUDSHELL_PASSWORD': cloudshell_password or 'None',
                    'CLOUDSHELL_DOMAIN': cloudshell_domain or 'None',
                    'CLOUDSHELL_RESERVATION_INFO': reservation_json or 'None',
                }
                if env_json:
                    env.update(env_json)
                output, robotretcode = self._process_runner.execute(tt, execution_id, env=env, directory=outdir)
            except Exception as uue:
                robotretcode = -5000
                output = 'Robot crashed: %s: %s' % (str(uue), traceback.format_exc())

            if robotretcode == -6000:
                return StoppedCommandResult()

            self._logger.debug('Result of %s: %d: %s' % (tt, robotretcode, string23(output)))

            if 'Data source does not exist' in output:
                return ErrorCommandResult('Robot failure', 'Test file %s/%s missing (at version %s). Original error: %s' % (outdir, test_path, git_branch_or_tag_spec or '[repo default branch]', output))

            if archive_output_xml_to:
                s = cdrip(archive_output_xml_to)
                os.makedirs(os.path.dirname(s), exist_ok=True)
                self._logger.info('Copying %s/output.xml to %s' % (outdir, s))
                shutil.copyfile('%s/output.xml' % outdir, s)

            zipname = '%s_%s.zip' % (test_path.replace(' ', '_').replace('/', '__'), now)
            try:
                zipoutput, _ = self._process_runner.execute_throwing([
                    'zip', '-j',
                    '%s/%s' % (outdir, zipname),
                    '%s/output.xml' % outdir,
                    '%s/log.html' % outdir,
                    '%s/report.html' % outdir
                ], execution_id+'_zip')
            except:
                return ErrorCommandResult('Robot failure', 'Robot did not complete: %s' % string23(output))

            with open('%s/%s' % (outdir, zipname), 'rb') as f:
                zipdata = f.read()

            if delete_output:
                self._logger.info('Deleting %s' % outdir)
                shutil.rmtree(outdir)

            if postprocessing_command:
                ppout, ppret = self._process_runner.execute(cdrip(postprocessing_command).split(' '), execution_id + '_postprocess')
                if ppret:
                    return ErrorCommandResult('Postprocessing failure', string23(ppout))

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
    try:
        print (msgstopping)
    except:
        pass
    try:
        subprocess.call(['wall', msgstopping])
    except:
        pass
    server.stop()
    logger.info(msgstopped)
    try:
        print (msgstopped)
    except:
        pass
    try:
        subprocess.call(['wall', msgstopped])
    except:
        pass

become_daemon_and_wait(daemon_start, daemon_stop)
