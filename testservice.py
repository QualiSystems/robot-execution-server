import json

import pythoncom
import signal

import time
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys

from cloudshell.custom_execution_server.custom_execution_server import CustomExecutionServer
from reference_custom_execution_server import MyCustomExecutionServerCommandHandler


class ServiceLogger:
    def warn(self, s):
        servicemanager.LogWarningMsg(s)
        # print(s + '\n')

    def debug(self, s):
        servicemanager.LogInfoMsg(s)
        # print(s + '\n')
        # pass

    def info(self, s):
        servicemanager.LogInfoMsg(s)
        # print(s + '\n')

    def error(self, s):
        servicemanager.LogErrorMsg(s)
        # print(s + '\n')

# with open(os.path.join(os.path.dirname(__file__), 'config.json')) as f:
#     o = json.load(f)

o = json.loads('''{
"host" : "http://localhost:9000",
"username" : "admin",
"password" : "admin",
"domain" : "Global",
"name" : "MyCES2",
"description" : "Reference implementation CES in Python",
"type" : "Python",
"capacity" : "5"
}
''')


class VerizonExecutionServerService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'VerizonExecutionServerService'
    _svc_display_name_ = 'Verizon Execution Server'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

        socket.setdefaulttimeout(60)

        self.isAlive = True

        self.server = CustomExecutionServer(server_name=o['name'],
                                       server_description=o['description'],
                                       server_type=o['type'],
                                       server_capacity=int(o['capacity']),

                                       command_handler=MyCustomExecutionServerCommandHandler(),

                                       logger=ServiceLogger(),

                                       cloudshell_host=o['host'].split('/')[-1].split(':')[0],
                                       cloudshell_port=int(o['host'].split('/')[-1].split(':')[1]),
                                       cloudshell_username=o['username'],
                                       cloudshell_password=o['password'],
                                       cloudshell_domain=o['domain'],

                                       auto_register=True,
                                       auto_start=False)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.server.stop()
        self.isAlive = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.isAlive = True
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ''))
        self.server.start()
        while self.isAlive:
            time.sleep(1)
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(VerizonExecutionServerService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(VerizonExecutionServerService)