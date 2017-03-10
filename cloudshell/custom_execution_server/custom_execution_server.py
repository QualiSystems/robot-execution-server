import json
import threading
from abc import abstractmethod
from time import sleep
import sys
import traceback

import itertools

import re

if sys.version_info.major == 2:
    from urllib2 import Request
    from urllib2 import urlopen
    from urllib import quote
else:
    from urllib.request import Request
    from urllib.request import urlopen
    from urllib.parse import quote


class CommandResult:
    """
    Base class for command results
    """
    def __init__(self):
        self.result = ''
        self.error_name = ''
        self.error_description = ''
        self.report_filename = ''
        self.report_data = ''
        self.report_mime_type = ''

    def __repr__(self):
        d = self.report_data
        try:
            if isinstance(self.report_data, bytes):
                d = '(binary data)'
        except:
            pass
        return '%s result=%s error_name=%s error_description=%s report_filename=%s report_data=<<<%s>>> report_mime_type=%s' % (self.__class__.__name__, self.result, self.error_name, self.error_description, self.report_filename, d, self.report_mime_type)


class StoppedCommandResult(CommandResult):
    """
    Result returned by the system when a stop request was received from CloudShellr
    """
    def __init__(self):
        CommandResult.__init__(self)
        self.result = 'Stopped'


class CompletedCommandResult(CommandResult):
    """
    Result that makes no comment on success or failure -- includes output file
    """
    def __init__(self, report_filename, report_data, report_mime_type='text/plain'):
        CommandResult.__init__(self)
        self.result = 'Completed'
        self.report_filename = report_filename
        self.report_data = report_data
        self.report_mime_type = report_mime_type


class PassedCommandResult(CommandResult):
    """
    Result of a test considered to have passed -- includes output file
    """
    def __init__(self, report_filename, report_data, report_mime_type='text/plain'):
        CommandResult.__init__(self)
        self.result = 'Passed'
        self.report_filename = report_filename
        self.report_data = report_data
        self.report_mime_type = report_mime_type


class FailedCommandResult(CommandResult):
    """
    Result of a test considered to have failed -- still includes output file
    """
    def __init__(self, report_filename, report_data, report_mime_type='text/plain'):
        CommandResult.__init__(self)
        self.result = 'Failed'
        self.report_filename = report_filename
        self.report_data = report_data
        self.report_mime_type = report_mime_type


class ErrorCommandResult(CommandResult):
    """
    Result to return when an error occurred -- includes error message and description but not an output file
    Also sent automatically by the system if the execute() implementation threw an exception
    """
    def __init__(self, error_name, error_description):
        CommandResult.__init__(self)
        self.result = 'Error'
        self.error_name = error_name
        self.error_description = error_description



class CustomExecutionServerCommandHandler:

    def __init__(self):
        pass

    @abstractmethod
    def execute(self, test_path, test_arguments, execution_id, username, reservation_id, reservation_json, logger):
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
        :param logger:
        :return: CommandResult : Use one of CommandResult subclasses - indicate success or failure, include report data
        :raises: Exception : Will be automatically caught and wrapped in ErrorCommandResult
        """
        raise Exception('ExecuteCommandHandler.execute() was not implemented')

    @abstractmethod
    def stop(self, execution_id, logger):
        """
        Send a message to a running execute() body corresponding to execution_id to signal it to exit

        :param execution_id:
        :param logger:
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

        self._running = False
        self._threads = []

        self._counter = itertools.count()

        self._token = None
        _, body = self._request('put', '/API/Auth/login',
                                    data=json.dumps({
                                        'Username': cloudshell_username,
                                        'Password': cloudshell_password,
                                        'Domain': cloudshell_domain,
                                    }))
        self._token = body.replace('"', '')

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
        self._threads = []
        self._running = True
        th = threading.Thread(target=self._status_update_thread)
        # th.daemon = True
        th.start()
        self._threads.append(th)
        th = threading.Thread(target=self._command_poll_thread)
        # th.daemon = True
        th.start()
        self._threads.append(th)

    def stop(self):
        self._running = False
        for th in self._threads:
            th.join()
        self._threads = []

    def _status_update_thread(self):
        while self._running:
            try:
                self._request('post', '/API/Execution/Status',
                              data=json.dumps({
                                  'Name': self._server_name,
                                  'ExecutionIds': list(self._execution_ids),
                              }))
            except Exception as e:
                self._logger.warn(str(e))

            for _ in range(60):
                sleep(1)
                if not self._running:
                    break

    def _command_poll_thread(self):
        while self._running:
            try:
                self._logger.info('Poll...')

                code, body = self._request('delete', '/API/Execution/PendingCommand',
                                  data=json.dumps({
                                      'Name': self._server_name,
                                  }))
                self._logger.info('Poll returned')
            except Exception as e:
                self._logger.warn('%s: Sleeping 30 seconds to wait for CloudShell to recover...' % str(e))
                sleep(30)
                continue

            if code == 204:
                continue

            o = json.loads(body)
            if not o:
                continue

            self._logger.debug('command request %s' % o)
            command_type = o['Type']
            execution_id = o['ExecutionId']
            if command_type == 'startExecution':
                resid = o.get('ReservationId', '')
                if resid:
                    _, reservation_json = self._request('get', '/API/Execution/Reservations/%s' % resid)
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
                self._command_handler.stop(execution_id, self._logger)
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
            self._logger.info(
                'Executing test_path=%s test_arguments=%s execution_id=%s username=%s reservation_id=%s reservation_json=%s' % (
                    test_path, test_arguments, execution_id, username, reservation_id, reservation_json))
            result = self._command_handler.execute(test_path, test_arguments, execution_id, username, reservation_id, reservation_json, self._logger)
        except:
            result = ErrorCommandResult('Unhandled Python exception', traceback.format_exc())

        if not result:
            result = ErrorCommandResult('Internal error', 'CustomExecutionServerCommandHandler.execute() should return a CommandResult object or throw an exception')

        self._logger.info('Result for execution %s: %s' % (execution_id, result))
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
                if sys.version_info.major == 3:
                    data = result.report_data
                    if isinstance(data, str):
                        data = data.encode('utf-8', 'replace')
                else:
                    data = result.report_data
                    if isinstance(data, unicode):
                        data = data.encode('utf-8', 'replace')

                self._request('post', '/API/Execution/ExecutionReport/%s/%s/%s' % (quote(self._server_name),
                                                                                   execution_id,
                                                                                   quote(result.report_filename)),
                              headers={
                                  'Accept': 'application/json',
                                  'Content-Type': result.report_mime_type,
                              },
                              data=data)
        finally:
            self._execution_ids.remove(execution_id)

    def _request(self, method, path, data=None, headers=None, **kwargs):
        if sys.version_info.major == 3:
            counter = self._counter.__next__()
        else:
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

        if sys.version_info.major == 3:
            if isinstance(data, bytes):
                pdata = '(%d bytes binary data)' % len(data)
            else:
                pdata = data
        else:
            pdata = data

        pdata = re.sub(r':[^@]*@', ':(password hidden)@', pdata)
        pdata = re.sub(r'"Password":\s*"[^"]*"', '"Password": "(password hidden)"', pdata)
        pheaders = dict(headers)
        if 'Authorization' in pheaders:
            pheaders['Authorization'] = '(token hidden)'

        self._logger.debug('Request %d: %s %s headers=%s data=<<<%s>>>' % (counter, method, url, pheaders, pdata))

        if sys.version_info.major == 3:
            if data:
                if isinstance(data, str):
                    data = data.encode('utf-8', 'replace')
            else:
                data = b''

        request = Request(url, data, headers)
        request.get_method = lambda: method.upper()
        response = urlopen(request)
        body = response.read()
        if sys.version_info.major == 3:
            if body:
                body = body.decode('utf-8')
            else:
                body = ''
        code = response.getcode()
        response.close()

        self._logger.debug('Result %d: %d: %s' % (counter, code, body))
        if code >= 400:
            raise Exception('Error: %d: %s' % (code, body))
        return code, body
