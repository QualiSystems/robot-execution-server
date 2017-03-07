"""Exposes the RESTful web service API as a python class."""

import urllib
import urllib2
import json
from os import path


class Api:
    def __init__(self, host, agent_name, agent_description, agent_type):
        """Initializes an instance of the CES API client.
        :param host: address (including port number) of the execution API on the TestShell server
        :param agent_name: The unique name of this execution server
        :param agent_description: Description of this execution server
        :param agent_type: The type of execution supported by this execution server
        :returns An instance of the API client class"""
        self._host = host
        self._agent_name = agent_name
        self._agent_description = agent_description
        self._agent_type = agent_type
        self._token_header = {}

    def _request(self, path, headers, data, http_method='POST', raw_data=False):
        headers['accept'] = 'application/json'
        headers['Content-Type'] = 'application/json'
        if not raw_data:
            data_string = json.dumps(data)
        else:
            data_string = data
        request = urllib2.Request(self._host + path, data_string.encode('utf8', 'replace'), headers)
        request.get_method = lambda: http_method
        response = urllib2.urlopen(request)
        page = response.read()
        return page

    def login(self, username, password, domain):
        """Logs in the execution server to the API, must be called before any other method."""
        response = self._request('/API/Auth/login', {}, {'Username': username, 'Password': password, 'Domain': domain}, 'PUT')
        self._token_header = {'Authorization': ('Basic ' + response.replace('"', ''))}

    def register(self, capacity):
        """Registers the execution server on the TestShell server.
        :param capacity: The number of concurrent executions supported by this execution server."""
        self._request('/API/Execution/ExecutionServers', self._token_header,
                      {'Name': self._agent_name, 'Description': self._agent_description,
                       'Type': self._agent_type, 'Capacity': capacity},
                      'PUT')

    def update(self, capacity):
        """Updates the details of this execution server on the TestShell server.
        :param capacity: The number of concurrent executions supported by this execution server."""
        self._request('/API/Execution/ExecutionServers', self._token_header,
                      {'Name': self._agent_name, 'Description': self._agent_description, 'Capacity': capacity},
                      'POST')

    def get_pending_command(self):
        """Retrieves (and removes) a single pending command from TestShell server.
        If none exists, the operation blocks on the server until a command is available or a timeout elapses.
        :returns A dictionary containing the command details or None if timed out.
        The command can be a start execution command, stop execution command or update-files command
        use the 'commandType' field to differentiate"""
        response = self._request('/API/Execution/PendingCommand', self._token_header, {'Name': self._agent_name},
                                 'DELETE')
        if response == '':
            return None
        return json.loads(response)

    def execution_ended(self, execution_id, result, error_description,
                        error_name, attachment_file_name, attachment_contents):
        """Report to the server that an execution has ended.
        :param execution_id: The Id of the ended execution as received in get_pending_execution.
        :param result: The result of the execution, one of [Completed, Passed, Failed, Stopped, Error].
        :param error_description: Free text description of the error if any.
        :param error_name: The name of the error if the result was Error.
        :param attachment_file_name: The name of the report to upload to the server as an attachment.
        :param attachment_contents: The contents of the attachment to upload.
        """
        execution_result = {'Name': self._agent_name, 'ExecutionId': execution_id,
                            'Result': result, 'ErrorDescription': error_description, 'ErrorName': error_name}
        self._request('/API/Execution/FinishedExecution', self._token_header, execution_result, 'PUT')
        if attachment_file_name != '':
			escaped_agent_name = urllib.quote(self._agent_name)
			# Get only the name of the file (without folder and ':' or '/')
			escaped_attachment_name = urllib.quote(path.split(attachment_file_name)[1])
			upload_url = '/API/Execution/ExecutionReport/{0}/{1}/{2}'.format(escaped_agent_name, execution_id, escaped_attachment_name)
			self._request(upload_url, self._token_header, attachment_contents, 'POST', True)

    def update_status(self, current_executions):
        """Ping the TestShell server with a list of the currently running executions."""
        execution_status = {'Name': self._agent_name, 'ExecutionIds': current_executions}
        self._request('/API/Execution/Status', self._token_header, execution_status)

    def update_files_ended(self, error_message):
        """Report to the TestShell server that updating to the latest version of the tests has completed.
        :param error_message: empty if the update was successful, otherwise, the reason of the failure.
        """
        update_files_status = {'Name': self._agent_name, 'ErrorMessage': error_message}
        self._request('/API/Execution/UpdateFilesEnded', self._token_header, update_files_status)

    def get_reservation_info(self, reservation_id):
        """Retrieves information about the reservation related to an execution.
        :param reservation_id: the id of the reservation that as appears in the job details."""
        response = self._request('/API/Execution/Reservations/{0}'.format(reservation_id), self._token_header,
                                 None, 'GET')
        if response == '':
            return None
        return json.loads(response)