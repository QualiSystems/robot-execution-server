import time


def test1_func(cloudshell_reservation_id, cloudshell_server_address, cloudshell_port, cloudshell_username, cloudshell_password, cloudshell_domain, cloudshell_reservation_json):
    print('hello from ericr_dev')
    print('CloudShell reservation id: %s' % cloudshell_reservation_id)
    print('CloudShell server address: %s' % cloudshell_server_address)
    print('CloudShell port: %d' % int(cloudshell_port))
    print('CloudShell admin username: %s' % cloudshell_username)
    print('CloudShell admin password: %s' % '(hidden)')
    print('CloudShell domain: %s' % cloudshell_domain)
    print('CloudShell reservation details: %s' % cloudshell_reservation_json)
    time.sleep(30)
