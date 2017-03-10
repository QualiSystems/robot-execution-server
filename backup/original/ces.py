#!/usr/bin/env python

"""The main module for the execution server."""

import utility
import sys
from time import sleep
from api import Api

current_executions = []
api = None
process_runner = utility.ProcessRunner()


def main():
    config = utility.load_configuration()
    global api
    api = Api(config['host'], config['name'], config['description'], config['type'])
    try:
        api.login(config['username'], config['password'], config['domain'])
    except Exception as ex:
        print('Login failed, error is ' + str(ex))
        sys.exit(1)
    print('Successfully Logged in.')
    utility.process_commandline_args(lambda: api.register(config['capacity']), lambda: api.update(config['capacity']))
    utility.run_background_thread(_update_status_loop)
    utility.run_background_thread(_get_command_loop)
    print ("Press enter to exit...")
    raw_input('')


def _update_status_loop():
    """Periodically updated TestShell server with currently running executions."""
    while True:
        try:
            api.update_status(current_executions)
        except Exception as ex:
            print('Unable to send status updates, error is ' + str(ex))
        sleep(60)


def _execute_job(job):
    """Perform the actual execution.
       This Implementation assumes testPath is the path to an executable and runs it.
       Other Implementations may interpret this data in a different way."""
    print("Received execution command triggered by " + job['UserName'])
    
    reservation_id = job.get('ReservationId')

    if reservation_id is not None:
        reservation_info = api.get_reservation_info(reservation_id)
        if reservation_info is not None:
            print('Retrieved reservation information:')
            print(str(reservation_info))  # Not used in this implementation. Can be passed to the execution in others.

    current_executions.append(job['ExecutionId'])  # Keep track of current executions for update_status_loop.
    if job['TestArguments'] is not None:
        command = '{0} {1}'.format(job['TestPath'], job['TestArguments'])
    else:
        command = job['TestPath']
    print ('Running ' + command)
    try:
        result = process_runner.execute(command, job['ExecutionId'])
        if result is not None:
            print ('Done running ' + command)
            error_description = 'Execution failed with exit code {0}'.format(str(result[1])) if result[1] else ''
            try:
                api.execution_ended(job['ExecutionId'], 'Failed' if result[1] else 'Passed',
                                    error_description,
                                    'badExitCode' if result[1] else '',
                                    job['TestPath'] + '.txt', result[0])
            except Exception as ex:
                sys.stdout.write('Unable to report end of execution, error is ' + str(ex) + '\n')
        else:
            print ('Stopped running ' + command)
            api.execution_ended(job['ExecutionId'], 'Stopped', '', '', '', '')
    except Exception as ex:
        print('Unable to execute command {0}, error is {1}'.format(command, str(ex)))
        try:
            api.execution_ended(job['ExecutionId'], 'Error', str(ex), 'CouldNotStart', '', '')
        except Exception as ex:
            print('Unable to report end of execution, error is ' + str(ex))
    current_executions.remove(job['ExecutionId'])  # Only after execution_ended was sent to the server.


def _update_files(update_files_user_parameters):
    """Perform any logic to retrieve the latest tests from source control here."""
    print("Received update local files command with the following parameters:")
    print(dir(update_files_user_parameters))
    print('Updating...')
    sleep(20)
    print('Done updating.')
    error_message = None
    api.update_files_ended(error_message)  # Report that the operation completed successfully .


def _stop_execution(execution_id):
    """Attempts to stops a currently running execution."""
    print("Received stop execution command.")
    process_runner.stop(execution_id)


def _get_command_loop():
    """Always look for the next command to be executed."""
    while True:
        try:
            command = api.get_pending_command()  # Blocks on the server until a command is available.
        except Exception as e:
            print('Unable to get command, error is ' + str(e))
            sleep(30)  # give server time to recover.
            continue
        if command is None:
            continue
        elif command['Type'] == 'startExecution':
            utility.run_background_thread(_execute_job, (command,))
        elif command['Type'] == 'stopExecution':
            _stop_execution(command['ExecutionId'])
        elif command['Type'] == 'updateFiles':
            _update_files(command['UserParameters'])


main()