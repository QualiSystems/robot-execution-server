import json
import threading
from abc import abstractmethod
from time import sleep
import requests
import itertools


class CommandResult:
    def __init__(self):
        self.result = ''
        self.error_name = ''
        self.error_description = ''
        self.report_filename = ''
        self.report_data = ''


class StoppedCommandResult(CommandResult):
    def __init__(self):
        CommandResult.__init__(self)
        self.result = 'Stopped'


class CompletedCommandResult(CommandResult):
    def __init__(self, report_filename, report_data):
        CommandResult.__init__(self)
        self.result = 'Completed'
        self.report_filename = report_filename
        self.report_data = report_data


class PassedCommandResult(CommandResult):
    def __init__(self, report_filename, report_data):
        CommandResult.__init__(self)
        self.result = 'Passed'
        self.report_filename = report_filename
        self.report_data = report_data


class ErrorCommandResult(CommandResult):
    def __init__(self, error_name, error_description):
        CommandResult.__init__(self)
        self.result = 'Error'
        self.error_name = error_name
        self.error_description = error_description


class FailedCommandResult(CommandResult):
    def __init__(self, error_name, error_description):
        CommandResult.__init__(self)
        self.result = 'Failed'
        self.error_name = error_name
        self.error_description = error_description


class CustomExecutionServerCommandHandler:
    @abstractmethod
    def execute(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json):
        """
        Executes the requested command.

        Should periodically check for a custom stop signal sent from your StopCommandHandler.stop(execution_id).

        Will be called in its own thread.

        Return an arbitrary CommandResult when the command completes, successfully or not.

        An exception can be thrown -- it will be automatically caught and wrapped in an ErrorCommandResult.

        :param test_path: str
        :param test_arguments: str
        :param execution_id: str
        :param username: str
        :param reservation_id: str : id of the reservation automatically reserved before starting the job
        :param reservation_json: str : If a reservation id was included, JSON describing the items in the reservation
        :return: CommandResult : Use one of CommandResult subclasses - indicate success or failure, include report data
        :raises: Exception : Will be automatically caught and wrapped in ErrorCommandResult
        """
        raise Exception('ExecuteCommandHandler.execute() was not implemented')

    @abstractmethod
    def stop(self, execution_id):
        """
        Send a message to a running execute() body corresponding to execution_id to signal it to exit

        :param execution_id:
        :return: None
        """
        pass


class CustomExecutionServer:
    def __init__(self, server_name, server_description, server_type, server_capacity,
                 command_handler,
                 logger,
                 cloudshell_host='localhost',
                 cloudshell_port=9000,
                 cloudshell_username='admin',
                 cloudshell_password='admin',
                 cloudshell_domain='Global',
                 auto_register=True,
                 auto_start=True):
        """

        :param server_name: str : unique name for registering execution server in CloudShell
        :param server_description: str : description to use when registering the execution server
        :param server_type: str : an execution server type registered manually in CloudShell beforehand
        :param server_capacity: int : number of concurrent commands CloudShell should send us

        :param command_handler: CommandHandler : your custom implementation of CommandHandler

        :param logger: logging.Logger

        :param cloudshell_host: str
        :param cloudshell_port: int
        :param cloudshell_username: str
        :param cloudshell_password: str
        :param cloudshell_domain: str

        :param auto_register: bool : automatically register this execution server in CloudShell from the constructor, ignoring 'already registered' error
        :param auto_start: bool : automatically start the server threads from in the constructor
        """
        self._cloudshell_host = cloudshell_host
        self._cloudshell_port = cloudshell_port
        self._cloudshell_username = cloudshell_username
        self._cloudshell_password = cloudshell_password
        self._cloudshell_domain = cloudshell_domain

        self._server_name = server_name
        self._server_description = server_description
        self._server_type = server_type
        self._server_capacity = server_capacity
        self._logger = logger

        self._command_handler = command_handler

        self._execution_ids = set()

        self._counter = itertools.count()

        self._token = None
        self._token = self._request('put', '/API/Auth/login',
                                    data=json.dumps({
                                        'Username': cloudshell_username,
                                        'Password': cloudshell_password,
                                        'Domain': cloudshell_domain,
                                    })).content.replace('"', '')

        if auto_register:
            try:
                self.register()
            except Exception as e:
                if 'already' in str(e):
                    self._logger.info('Ignoring error: %s' % str(e))
                else:
                    raise e

        if auto_start:
            self.start()

    def register(self):
        """
        Registers the server
        :return:
        """
        self._request('put', '/API/Execution/ExecutionServers',
                      data=json.dumps({
                          'Name': self._server_name,
                          'Description': self._server_description,
                          'Type': self._server_type,
                          'Capacity': self._server_capacity,
                      }))

    def update(self):
        self._request('post', '/API/Execution/ExecutionServers',
                      data=json.dumps({
                          'Name': self._server_name,
                          'Description': self._server_description,
                          'Capacity': self._server_capacity,
                      }))

    def start(self):
        th = threading.Thread(target=self._status_update_thread)
        th.daemon = True
        th.start()
        th = threading.Thread(target=self._command_poll_thread)
        th.daemon = True
        th.start()

    def _status_update_thread(self):
        while True:
            try:
                self._request('post', '/API/Execution/Status',
                              data=json.dumps({
                                  'Name': self._server_name,
                                  'ExecutionIds': list(self._execution_ids),
                              }))
            except Exception as e:
                self._logger.warn(str(e))
            sleep(60)

    def _command_poll_thread(self):
        while True:
            try:
                self._logger.info('Poll...')
                r = self._request('delete', '/API/Execution/PendingCommand',
                                  data=json.dumps({
                                      'Name': self._server_name,
                                  }))
                self._logger.info('Poll returned')
            except:
                self._logger.warn('Sleeping 30 seconds to wait for CloudShell to recover...')
                sleep(30)
                continue

            if r.status_code == 204:
                continue

            o = json.loads(r.content)
            if not o:
                continue

            self._logger.debug('command request %s' % o)
            command_type = o['Type']
            execution_id = o['ExecutionId']
            if command_type == 'startExecution':
                resid = o.get('ReservationId', '')
                if resid:
                    r = self._request('get', '/API/Execution/Reservations/%s' % resid)
                    reservation_json = r.content
                else:
                    reservation_json = ''

                th = threading.Thread(target=self._command_worker_thread, args=(
                    o.get('TestPath', ''),
                    o.get('TestArguments', ''),
                    execution_id,
                    o.get('UserName', ''),
                    resid,
                    reservation_json
                ))
                th.daemon = True
                th.start()
            elif command_type == 'stopExecution':
                self._command_handler.stop(execution_id)
            elif command_type == 'updateFiles':
                # Must send this response or the execution server will be disabled
                self._request('post', '/API/Execution/UpdateFilesEnded',
                              data=json.dumps({
                                  'Name': self._server_name,
                                  'ErrorMessage': ''
                              }))

    def _command_worker_thread(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json):
        self._execution_ids.add(execution_id)
        try:
            result = self._command_handler.execute(test_path, test_arguments, execution_id, username, reservation_id, reservation_json)
        except Exception as e:
            result = ErrorCommandResult('Unhandled Python exception', str(e))

        try:
            self._request('put', '/API/Execution/FinishedExecution',
                          data=json.dumps({
                              'Name': self._server_name,
                              'ExecutionId': execution_id,
                              'Result': result.result,
                              'ErrorDescription': result.error_description,
                              'ErrorName': result.error_name,
                          }))
            if result.report_filename:
                self._request('post', '/API/Execution/ExecutionReport/%s/%s/%s' % (requests.utils.quote(self._server_name),
                                                                                   execution_id,
                                                                                   requests.utils.quote(result.report_filename)),
                              headers={
                                  'Accept': 'application/json',
                                  'Content-Type': 'application/octet-stream',
                              },
                              data=result.report_data)
        finally:
            self._execution_ids.remove(execution_id)

    def _request(self, method, path, data=None, headers=None, **kwargs):
        counter = self._counter.next()
        if not headers:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            }
        if self._token:
            headers['Authorization'] = 'Basic ' + self._token

        if path.startswith('/'):
            path = path[1:]

        url = 'http://%s:%d/%s' % (self._cloudshell_host, self._cloudshell_port, path)

        self._logger.debug('Request %d: %s %s headers=%s data=<<<%s>>>' % (counter, method, url, headers, data))

        rv = requests.request(method, url, data=data, headers=headers, **kwargs)
        self._logger.debug('Result %d: %d: %s' % (counter, rv.status_code, rv.content))
        if rv.status_code >= 400:
            raise Exception('Error: %d: %s' % (rv.status_code, rv.content))
        return rv
