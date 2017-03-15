def test_fail_func(cloudshell_reservation_id, cloudshell_server_address, cloudshell_port, cloudshell_username, cloudshell_password, cloudshell_domain):
    print('hello from ericr_dev')
    print('CloudShell reservation id: %s' % cloudshell_reservation_id)
    print('CloudShell server address: %s' % cloudshell_server_address)
    print('CloudShell port: %d' % int(cloudshell_port))
    print('CloudShell admin username: %s' % cloudshell_username)
    print('CloudShell admin password: %s' % '(hidden)')
    print('CloudShell domain: %s' % cloudshell_domain)
    raise Exception('failure test')
