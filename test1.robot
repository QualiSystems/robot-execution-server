*** Settings ***
Documentation     Example testcase demonstrating CloudShell integration
Library           robot_test1.py

*** Variables ***
${CLOUDSHELL_RESERVATION_ID}  error-reservation-id-not-set
${CLOUDSHELL_SERVER_ADDRESS}  error-cloudshell-server-not-set
${CLOUDSHELL_SERVER_PORT}     8029
${CLOUDSHELL_USERNAME}        error-cloudshell-user-not-set
${CLOUDSHELL_PASSWORD}        error-cloudshell-password-not-set
${CLOUDSHELL_DOMAIN}          error-cloudshell-domain-not-set

*** Test Cases ***
Test1
    test1_func  ${CLOUDSHELL_RESERVATION_ID}  ${CLOUDSHELL_SERVER_ADDRESS}  ${CLOUDSHELL_SERVER_PORT}  ${CLOUDSHELL_USERNAME}  ${CLOUDSHELL_PASSWORD}  ${CLOUDSHELL_DOMAIN}
