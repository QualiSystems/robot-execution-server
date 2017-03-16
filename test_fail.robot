*** Settings ***
Documentation     Example testcase demonstrating CloudShell integration
Library           robot_test_fail.py

*** Variables ***
${CLOUDSHELL_RESERVATION_ID}   %{CLOUDSHELL_RESERVATION_ID}
${CLOUDSHELL_SERVER_ADDRESS}   %{CLOUDSHELL_SERVER_ADDRESS}
${CLOUDSHELL_SERVER_PORT}      %{CLOUDSHELL_SERVER_PORT}
${CLOUDSHELL_USERNAME}         %{CLOUDSHELL_USERNAME}
${CLOUDSHELL_PASSWORD}         %{CLOUDSHELL_PASSWORD}
${CLOUDSHELL_DOMAIN}           %{CLOUDSHELL_DOMAIN}
${CLOUDSHELL_RESERVATION_INFO} %{CLOUDSHELL_RESERVATION_INFO}

*** Test Cases ***
Test1
    test_fail_func  ${CLOUDSHELL_RESERVATION_ID}  ${CLOUDSHELL_SERVER_ADDRESS}  ${CLOUDSHELL_SERVER_PORT}  ${CLOUDSHELL_USERNAME}  ${CLOUDSHELL_PASSWORD}  ${CLOUDSHELL_DOMAIN}  ${CLOUDSHELL_RESERVATION_INFO}
