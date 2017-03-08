import json
import os
import sys

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServerCommandHandler, \
    CustomExecutionServer, PassedCommandResult


class Handler(CustomExecutionServerCommandHandler):

    def __init__(self):
        CustomExecutionServerCommandHandler.__init__(self)

    def execute(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
        # logger.info('execute %s %s %s %s %s %s\n' % (test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
        res = json.loads(reservation_json)
        tag = '(TestVersion environment input missing)'
        for inp in res['TopologyInputs']:
            if inp['Name'] == 'TestVersion':
                tag = inp['Value']
        logger.info('Version to check out from BitBucket: "%s"' % tag)
        logger.info('Test path: %s' % test_path)
        logger.info('Test arguments: %s' % test_arguments)
        return PassedCommandResult('report.txt', 'x')

    def stop(self, execution_id, logger):
        pass


class Logger:
    def warn(self, s):
        print(s + '\n')
    def debug(self, s):
        # print(s + '\n')
        pass
    def info(self, s):
        print(s + '\n')
    def error(self, s):
        print(s + '\n')

with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
    o = json.load(f)

server = CustomExecutionServer(server_name=o['name'],
                               server_description=o['description'],
                               server_type=o['type'],
                               server_capacity=int(o['capacity']),

                               command_handler=Handler(),

                               logger=Logger(),

                               cloudshell_host=o['host'].split('/')[-1].split(':')[0],
                               cloudshell_port=int(o['host'].split('/')[-1].split(':')[1]),
                               cloudshell_username=o['username'],
                               cloudshell_password=o['password'],
                               cloudshell_domain=o['domain'],

                               auto_register=True,
                               auto_start=True)
print ("\n\n\nPRESS <ENTER> TO EXIT...\n\n\n")
if sys.version_info.major == 2:
    raw_input()
else:
    input()
print ("Stopping, please wait up to 2 minutes...")
server.stop()
print ("Stopped")
