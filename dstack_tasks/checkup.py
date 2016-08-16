import logging
import os
import re
import shutil
import sys
from typing import Callable

from fabric.api import env
from fabric.colors import red, green, yellow, white
from fabric.decorators import task

from dstack_tasks.utils import get_result

dependency_versions = {
    'git': '2.7.1',
    'python': '3.5.1',
    'conda': '3.14.1',
    'pip': '8.0.2',
    # 'rsync': '2.6.9',
    'wget': '1.17.1',
    'curl': '7.43.0',
    'grep': '2.5.1',
    'ssh': '1',
    'docker': '1.10.1',
    'docker-compose': '1.6.0',
    'docker-machine': '0.6.0',
    'fab': '1.10.2',
    'brew': '0.9.5',
}


def checkup(check_function: Callable[[None], dict], description: str = 'Checking...',
            success: str = 'No problem', error: str = 'Errors found'):
    if env.log_level <= logging.DEBUG:
        print(description)

    result = check_function()

    if result['success']:
        if env.log_level <= logging.INFO:
            print(green(success))
    else:
        if env.log_level <= logging.WARNING:
            print(red(error, bold=True))


def check_dependencies():
    success = True

    dependencies = [
        'git', 'python', 'conda', 'pip', 'rsync', 'wget', 'curl', 'grep', 'ssh',
        'docker', 'docker-compose', 'docker-machine', 'fab', 'node', 'bower'
    ]

    if os.name == 'nt':
        dependencies += ['choco', ]
    elif sys.platform == 'darwin':
        dependencies += ['brew', ]

    unmet = 0

    for dependency in dependencies:
        path = shutil.which(dependency)
        version = ['', ]
        if path:
            if dependency not in ['ssh', ]:
                version_raw = get_result(path + ' --version')
                try:
                    version = re.findall(r'\d+\.\d+\.\d?', version_raw.stderr if version_raw.stderr else version_raw)
                except:
                    pass
            if not version:
                version = ['', ]

            if env.log_level <= logging.DEBUG:
                print('{0} {1:15} {2:20} {3}'.format(
                    green(' O', bold=True), dependency, yellow(version[0], bold=True), os.path.abspath(path)))
        else:
            if env.log_level <= logging.WARNING:
                print(red(' X', bold=True), ' ', dependency)

            unmet += 1

    if unmet > 0:
        success = False

    return {'success': success, }


def check_virtual_env():
    success = True

    conda_envs = get_result('conda info --envs')
    conda_envs = conda_envs.split('\n')[2:]

    for cenv in conda_envs:
        project_env_line = cenv.find(env.virtual_env) != -1

        if cenv.find('*') and project_env_line:
            if env.log_level <= logging.INFO:
                print(green('Project environment found and active:'))
                print(white(cenv))
        elif project_env_line:
            if env.log_level <= logging.WARNING:
                print(yellow('Project environment found, but not activated'))
                print(white('To fix, run:\n > activate <venv>'))
            success = False

    return {'success': success, }


def check_default_machine():
    if env.log_level <= logging.INFO:
        print(white('\nDocker checkup', bold=True))

    env_cmd = {
        'nt': 'FOR /f "tokens=*" %i IN (\'docker-machine env default\') DO %i',
        'posix': 'eval $(docker-machine env default)'
    }

    line = red('#' * 74)

    # check3 = 0
    default_machine = get_result('docker-machine ls --filter name=default')
    machines = default_machine.split('\n')
    if len(machines) > 1:
        default_machine = machines[1]
        if default_machine.find('Running') != -1 and default_machine.find('*') != -1:
            if env.log_level <= logging.INFO:
                print(green('Default machine running and active'))
        elif default_machine.find('Running') != -1 and default_machine.find('-') != -1:
            if env.log_level <= logging.INFO:
                print(yellow('Warning: Default machine running but not active'))
                print(line)
                print(' > ' + env_cmd[env.os])
                print(line)
        else:
            if env.log_level <= logging.INFO:
                print(yellow('Warning: Default machine found but not running'))
                print(line)
                print(' > docker-machine start default')
                print(' > ' + env_cmd[env.os])
                print(line)

    else:
        if env.log_level <= logging.WARNING:
            print(red('Error: Default machine does not exist'))
            print(line)
            print(white('Create using:\n > docker-machine create --driver virtualbox default'))
            print(' > docker-machine start default')
            print(' > ' + env_cmd[env.os])
            print(line)


def check_env_vars():
    if env.log_level <= logging.INFO:
        print(white('\nEnvironment checkup', bold=True))

    envs = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy', 'conda_default_env']
    for e in envs:
        value = os.environ.get(e, '')
        if value:
            if env.log_level <= logging.INFO:
                print('{0} {1:15} = {2:20}'.format(
                    yellow(' >', bold=True), e, yellow(value, bold=True)))
        else:
            if env.log_level <= logging.INFO:
                print('{0} {1:15}'.format(
                    yellow(' >', bold=True), e))

    if env.log_level <= logging.INFO:
        print(green('Everything is looking good!'))

    if env.log_level <= logging.INFO:
        print(white('\nChecking for .env file', bold=True))

    # mandatory_envs = ['SITE_ID', 'DEBUG']
    if os.path.exists('./.env'):
        if env.log_level <= logging.INFO:
            print(green('Found .env file'))
        os.environ.get('PATH', '')
    else:
        if env.log_level <= logging.ERROR:
            print(red('.env does not exist!'))


def check_postgres():
    # docker-machine ssh {host_name} -C "echo `pbpaste` >> .ssh/authorized_keys"

    if env.log_level <= logging.INFO:
        print(white('\nChecking for postgres entry in hosts file', bold=True))
    try:
        import socket
        ip = socket.gethostbyname('postgres')
        if ip:
            if env.log_level <= logging.INFO:
                print(green("Postgres IP is %s" % ip))
    except:
        if env.log_level <= logging.ERROR:
            print(red("Hostname not set!"))


@task
def doctor() -> None:
    """ Checks the health of your project

    :return: None
    """
    checkup(check_virtual_env,
            description='Python virtualenv checkup...',
            success='Everything is looking good',
            error='Project environment does not exist. To fix, run\n > conda env create -f etc/environment.yml', )

    check_default_machine()
    check_env_vars()
    check_postgres()

    checkup(check_dependencies,
            description='Checking dependencies...',
            success='All dependencies installed',
            error='Please install missing dependencies', )
