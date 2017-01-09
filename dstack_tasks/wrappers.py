"""Fabric task wrappers to interact with most development tools like docker, git, etc.

TODO:
    Remove all hardcoded references to "src" and prepare to depreecate the ``project_name/src`` project structure
    in favour of ``project_name/project_name``.

    The end-goal is to be able to package webapps with its' manage.py file exposed as a console script.
    This will require all webapps to be updated to use import links like ``project_name.module.function``
    instead of ``.module.function`` where applicable.

"""
import importlib
import logging
import os
import posixpath
from distutils.util import strtobool
from pathlib import Path

from fabric.colors import green, yellow, red
from fabric.context_managers import cd, prefix
from fabric.decorators import task
from fabric.operations import run, local, get, put, prompt
from fabric.state import env
from fabric.tasks import execute as fab_exec

from .utils import check_keys


@task
def dotenv(action: str = None, key: str = None, value: str = None, live: bool = False) -> None:
    """Manage project configuration via .env

    e.g: fab config:set,<key>,<value>
         fab config:get,<key>
         fab config:unset,<key>
         fab config:list
    """
    if live:
        dot_path = env.server_dotenv_path
    else:
        dot_path = env.local_dotenv_path

    try:
        from dotenv import get_cli_string
    except ImportError:
        get_cli_string = 'Error'
        if env.log_level <= logging.INFO:
            print(get_cli_string, 'To manage .env files, you need to first install dotenv:')
            print('pip install -U python-dotenv')
    else:
        execute('touch %s' % dot_path, live=live)
        command = dotenv.get_cli_string(dot_path, action, key, value)
        execute(command, live=live)


# @task
# def execute_on(host: str, task_name: str):
#     tasks = importlib.import_module('dstack_tasks')
#     task_instance = getattr(tasks, task_name)
#
#     if not env.dry:
#         fab_exec(task=task_instance, host=host)
#     else:
#         task_instance()


@task
def execute(cmd: str = '--help', path: str = None, live: bool = False, **kwargs):
    """ Wrapper for both local and remote tasks optionally setting the execution path.

    Args:
        cmd:
        path:
        live:
        **kwargs:

    """

    if not isinstance(live, bool):
        live = bool(strtobool(live))

    if path is None:
        path = env.project_dir if live else ''
    # print(path)
    with cd(path):
        env.pwd = path
        run(cmd, **kwargs) if live else local(cmd, **kwargs)


@task
def compose(cmd: str = '--help', image_tag: str = None, path: str = None, live: bool = False) -> None:
    """docker-compose wrapper

    Args:
        cmd: Command
        image_tag: Image tag
        path: path
        live: Live or local.

    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    env.image_tag = image_tag or env.image_tag
    check_keys(env, ['image_name', 'image_tag'])

    base_cmd = '{env_vars}docker-compose {cmd}'
    template = {
        'posix': 'export UID; IMAGE={image_name}:{image_tag} ',
        'nt': 'set PWD=%cd%&& set IMAGE={image_name}:{image_tag} && ',
    }

    cmd_string = base_cmd.format(env_vars=template[os.name if not live else 'posix'].format(**env), cmd=cmd)

    try:
        execute(cmd=cmd_string, path=path, live=live)
    except SystemExit:
        pass


@task
def docker(cmd: str = '--help', path: str = None, live: bool = False) -> None:
    """Task wrapping docker

    Args:
        cmd: The docker command to run.
        path: The path in which the docker command should be executed.
            Needed when building images or copying files.
        live:

    """
    if path is None:
        path = ''
        # path = env.get('project_dir', '')

    execute(cmd='docker {cmd}'.format(cmd=cmd), path=path, live=live)


@task
def manage(cmd: str = 'help', live: bool = False, package: bool = False) -> None:
    """Task wrapping python src/manage.py

    Args:
        package: whether manage.py is in a folder named after the package or under ``src``
        cmd: The manage.py command to run.
        live:

    """
    if live:
        # TODO: Make _staging generic or apply to others as well
        compose('run --rm webapp bash -c "python manage.py {cmd}"'.format(cmd=cmd), live=True)
    else:
        # TODO: remove hardcoded src, replace with project name
        with prefix(env.activate):
            if not package:
                local('python src/manage.py {cmd}'.format(cmd=cmd))
            else:
                local('python {project_name}/manage.py {cmd}'.format(cmd=cmd, project_name=env.project_name))


@task
def pip(cmd: str = '--help') -> None:
    """Task wrapping pip

    Args:
        cmd: The pip command to run.

    """
    with prefix(env.activate):
        local('pip {cmd}'.format(cmd=cmd))


@task
def conda(cmd: str = '--help') -> None:
    """Task wrapping conda

    Args:
        cmd: The conda command to run.

    """
    with prefix(env.activate):
        local('conda {cmd}'.format(cmd=cmd))


@task
def filer(cmd: str = 'get',
          local_path: str = None, remote_path: str = None,
          file: str = '.env', use_sudo: bool = False) -> None:
    """Specifying a remote_path or a local_path overrides the "file" parameter.

    Args:
        cmd: Either "get" or "put". Corresponds with the "get" and "put" Fabric tasks.
        local_path: Path to local file
        remote_path: Path to remote file
        file: Shortcut if it is a file that needs to be copied to its corresponding project location
        use_sudo: Prompts for sudo password to run the command with elevated privileges.

    Raises:
        AttributeError: Raised if neither `file` nor local and remote paths where specified.

    """

    if file:
        remote_path = remote_path or posixpath.join(env.project_dir, file)
        local_path = local_path or file
    else:
        if not remote_path or local_path:
            raise AttributeError('Must specify remote_path and local_path if file is not used')

    if cmd == 'get':
        get(remote_path=remote_path, local_path=local_path, use_sudo=use_sudo)
    elif cmd == 'put':
        put(local_path=local_path, remote_path=remote_path, use_sudo=use_sudo)
        execute('chmod go+r {0}'.format(remote_path), path='', live=True)


@task
def postgres(cmd: str = 'backup', live: bool = False, tag: str = 'tmp', sync_prompt: bool = False):
    """Task for backup and restore of postgres database

    Args:
        cmd: either backup or restore.
        live:
        tag:
        sync_prompt: Whether to prompt for downloading or uploading backups.
            **Deprecated** in favor of S3 based solution to prevent direct upload and downloading of large files.

    Todo:
        * This tasks needs to be optimized to use postgres tools like mysql_dump and needs
        * It also needs to be generalized to allow MySQL backups and syncing to S3 (or other storage)

    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    backup_name = 'db_backup.{tag}.tar.gz'.format(tag=tag)

    backup_path = posixpath.join('/backup/', backup_name)
    actions = {
        'backup': 'tar -zcpf %s /data' % backup_path,
        'restore': 'bash -c "tar xpf %s && chmod -R 700 /data"' % backup_path,
    }

    # The assumption is that 'live' will always be on unix server
    if live:
        backup_to_path = posixpath.join(env.project_dir, 'var/backups')
    else:
        backup_to_path = os.path.join(env.project_path, 'var/backups')
        if os.name == 'nt':
            backup_to_path = posixpath.join('/c/', Path(backup_to_path).as_posix()[3:])

    params = {
        'data': '-v %s_dbdata:/data' % env.project_name.replace('.', '').replace('_', ''),
        'backup': '-v %s:/backup' % backup_to_path,
        'cmd': actions[cmd],
    }

    if sync_prompt:
        if live and cmd == 'restore':
            answer = prompt('Do you first want to upload the backup?', default='no', )
            if answer == 'yes':
                with cd(env.project_dir):
                    run('mkdir -p var/backups')
                filer(cmd='put', file=os.path.join('var/backups/', backup_name), use_sudo=True)

        if not live and cmd == 'restore':
            answer = prompt('Do you first want to download the backup?', default='no', )
            if answer == 'yes':
                filer(cmd='get', file=posixpath.join('var/backups/', backup_name))

    compose('stop postgres', live=live)
    docker('run --rm {data} {backup} postgres:9.5 {cmd}'.format(**params), live=live)
    compose('start postgres', live=live)

    if live and cmd == 'backup':
        if sync_prompt:
            answer = prompt('Did you want to download backup?', default='no', )
            if answer == 'yes':
                filer(cmd='get', file=posixpath.join('var/backups/', backup_name))


@task
def bower(component: str = 'rebuild') -> None:
    """Task wrapping bower. If component is specified, install and saves to the bower.json file.

    Args:
        component: The bower component to be installed

    """
    if component != 'rebuild':
        local('bower install --save {0}'.format(component))

    local(os.path.join(env.node_modules, 'bower-requirejs') + ' -c src/static/js/config.js')
    local(os.path.join(env.node_modules, 'r.js') + ' -o src/static/js/build.js')

    manage('collectstatic --noinput -v1')


@task
def npm(package: str = 'install'):
    """Task wrapping npm

    Args:
        package: specifies the npm pacakge to install.

    """
    if package == 'install':
        local('npm install --only=dev --prefix bin')
    else:
        local('npm install --save-dev {0} --prefix bin'.format(package))


@task
def git(cmd: str = '--help', path: str = None, live: bool = False):
    """Task wrapping git.

    Args:
        cmd: The git command to run.
        path: Required only when git cloning for the first time.
        live:

    Returns:

    """
    execute('git {cmd}'.format(cmd=cmd), live=live, path=path)


@task
def s3(cmd: str = 'help') -> None:
    """Task wrapping the "aws s3" interface.

    Note:
        Requires that awscli be installed and configured and available in the path.

    Args:
        cmd: The aws s3 command to run.
    """

    # TODO: Raise error if awscli is not installed
    execute('aws s3 {cmd}'.format(**locals()))


@task
def docker_exec(service='postgres', cmd: str = 'bash', live: bool = False):
    """Function that wraps the docker exec interface.
    This task reduces the amount of boiler plate needed to execute tasks in docker containers
    spawned by docker-compose.


    Args:
        service: typically the name of the project with spaces, underscores, etc removed.
           E.g. project_name becomes projectname.
        cmd: The command to be executed in the docker container.
        live:

    Returns:

    """
    env.service = service
    env.cmd = cmd
    docker(cmd='exec -it {project_name}_{service}_1 {cmd}'.format(**env), live=live)


@task
def loaddata(live: bool = False, app: str = 'config', file_name='initial_data', extension: str = 'json'):
    """

    Args:
        live:
        app: which app
        file_name: Defaults to initial_data.
        extension: Default is json. Yaml is also supported if PyYaml is installed.

    Returns:

    """
    manage('migrate', live=live)
    path = 'src/' if not live else ''
    manage('loaddata {path}{app}/fixtures/{file_name}.{extension}'.format(**locals()), live=live)


@task
def dry(dry_run: bool = True) -> None:
    """Show, but don't run fabric commands"""
    global local, run, get, put

    env.dry = True

    if dry_run:
        # Redefine the local and run functions to simply output the command
        def local(command, capture=False, shell=None):
            print(green('(dry) '), yellow('[localhost] '), 'cd %s && ' % env.pwd if env.pwd else '', '%s' % command,
                  sep='')

        def run(command, shell=True, pty=True, combine_stderr=None, quiet=False,
                warn_only=False, stdout=None, stderr=None, timeout=None, shell_escape=None,
                capture_buffer_size=None):
            print(green('(dry) '), red('[%s] ' % env.host_string), 'cd %s && ' % env.pwd if env.pwd else '',
                  '%s' % command, sep='')

        def get(remote_path, local_path=None, use_sudo=False, temp_dir=""):
            host = env.host_string
            print(green('(dry) '), red('[{}] '.format(host)),
                  'scp {host}:{remote_path} {local_path}'.format(**locals()), sep='')

        def put(remote_path, local_path=None, use_sudo=False, temp_dir=""):
            host = env.host_string
            print(green('(dry) '), red('[{}] '.format(host)),
                  'scp {local_path} {host}:{remote_path}'.format(**locals()), sep='')
