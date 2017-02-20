"""Fabric task wrappers to interact with most development tools like docker, git, etc.

TODO:
    Remove all hardcoded references to "src" and prepare to depreecate the ``project_name/src`` project structure
    in favour of ``project_name/project_name``.

    The end-goal is to be able to package webapps with its' manage.py file exposed as a console script.
    This will require all webapps to be updated to use import links like ``project_name.module.function``
    instead of ``.module.function`` where applicable.

"""
import logging
import os
import posixpath
from distutils.util import strtobool
from pathlib import Path

from fabric.colors import green, red, yellow
from fabric.context_managers import cd, prefix
from fabric.decorators import task
from fabric.operations import local, run, get, put, prompt
from fabric.state import env

from .utils import check_keys, dirify


@task
def dotenv(action: str = None, key: str = None, value: str = None, live: bool = None, env_file: str = None) -> None:
    """Manage project configuration via .env

    e.g: fab config:set,<key>,<value>
         fab config:get,<key>
         fab config:unset,<key>
         fab config:list
    """
    if live is None:
        live = env.live

    if live:
        if env_file:
            project_dir = dirify(env.project_dir, force_posix=True)
            dot_path = project_dir(env_file)
        else:
            dot_path = env.server_dotenv_path

    else:
        if env_file:
            project_path = dirify(env.project_path)
            dot_path = project_path(env_file)
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
        command = get_cli_string(dot_path, action, key, value)

        d, e = command.split(sep=' ', maxsplit=1)
        command = d + ' -q auto ' + e

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
def execute(cmd: str = '--help', path: str = None, live: bool = None, **kwargs):
    """ Wrapper for both local and remote tasks optionally setting the execution path.

    Args:
        cmd:
        path:
        live:
        **kwargs:

    """
    if live is None:
        live = env.live

    if path is None:
        path = env.project_dir if live else ''

    if path != '':
        with cd(path):
            env.pwd = path
            run(cmd, **kwargs) if live else local(cmd, **kwargs)
    else:
        env.pwd = None
        run(cmd, **kwargs) if live else local(cmd, **kwargs)


@task
def compose(cmd: str = '--help', instance: str = None, path: str = None, live: bool = None) -> None:
    """docker-compose wrapper

    Args:
        cmd: Command
        instance: Image tag
        path: path
        live: live

    """
    check_keys(env, ['image_name', 'tag'])

    if live is None:
        live = env.live

    # Update tag with instance. Note that env.version does not change
    if instance:
        env.tag = '{tag}-{instance}'.format(tag=env.tag, instance=instance)

    base_cmd = '{env_vars}docker-compose {cmd}'
    template = {
        'posix': 'export UID; IMAGE={image_name}:{tag} ',
        'nt': 'set PWD=%cd%&& set IMAGE={image_name}:{tag} && ',
    }

    cmd_string = base_cmd.format(
        env_vars=template[os.name if not env.live else 'posix'].format(**env), cmd=cmd)

    try:
        execute(cmd=cmd_string, path=path, live=live)
    except SystemExit:
        pass


@task
def docker(cmd: str = '--help', path: str = None, live: bool = None) -> None:
    """Task wrapping docker

    Args:
        cmd: The docker command to run.
        path: The path in which the docker command should be executed.
            Needed when building images or copying files.
        live:

    """
    if live is None:
        live = env.live

    if path is None:
        path = ''
        # path = env.get('project_dir', '')

    execute(cmd='docker {cmd}'.format(cmd=cmd), path=path, live=live)


@task
def manage(cmd: str = 'help', live: bool = None) -> None:
    """Task wrapping python src/manage.py

    Args:
        cmd: The manage.py command to run.
        live:

    """
    if live is None:
        live = env.live

    if live:
        # TODO: Make _staging generic or apply to others as well
        compose('run --rm webapp bash -c "python manage.py {cmd}"'.format(cmd=cmd), live=live)
    else:
        with prefix(env.activate):
            local('python {package}/manage.py {cmd}'.format(cmd=cmd, package=env.src))


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
          file: str = '.env', use_sudo: bool = False, fix_perms: bool = True) -> None:
    """Specifying a remote_path or a local_path overrides the "file" parameter.

    Args:
        cmd: Either "get" or "put". Corresponds with the "get" and "put" Fabric tasks.
        local_path: Path to local file
        remote_path: Path to remote file
        file: Shortcut if it is a file that needs to be copied to its corresponding project location
        use_sudo: Prompts for sudo password to run the command with elevated privileges.
        fix_perms: Default = True. Whether to add read permission for group and other users.

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
        if fix_perms:
            execute('chmod -R go+r {0}'.format(remote_path), path='', live=True)


@task
def postgres(cmd: str = 'backup', live: bool = None, tag: str = 'tmp', sync_prompt: bool = False):
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
    if live is None:
        live = env.live

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
        backup_to_path = os.path.join(env.pwd, 'var/backups')
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
def git(cmd: str = '--help', path: str = None, live: bool = None):
    """Task wrapping git.

    Args:
        cmd: The git command to run.
        path: Required only when git cloning for the first time.
        live:

    Returns:

    """
    if live is None:
        live = env.live

    execute('git {cmd}'.format(cmd=cmd), live=live, path=path)


@task
def s3(cmd: str = 'help', live: bool = None) -> None:
    """Task wrapping the "aws s3" interface.

    Note:
        Requires that awscli be installed and configured and available in the path.

    Args:
        cmd: The aws s3 command to run.
        live: run os server or local
    """
    if live is None:
        live = env.live

    # TODO: Raise error if awscli is not installed
    execute('aws s3 {cmd}'.format(cmd=cmd, live=live), path='')


@task
def s3cp(simple_path: str = None, direction: str = 'up', local_path: str = None, s3_path: str = None,
         bucket: str = 's3://dstack-storage', live: bool = None) -> None:
    """Wrapper for copying files to and from s3 bucket.

    Args:
        simple_path: If specified, constructs local_path and s3_uri from relative path provided, keeping same directory
            structure on s3 and locally.
        direction: `up` or `down`.
        bucket: Default s3://dstack-storage.
        local_path: Local relative path
        s3_path: Path on s3 bucket.
        live: Run local or on server. If live = True, then "local_path" means local path on server.

    Returns:

    Raises:
        AttributeError: When neither simple_path nor s3_path and local_path are specified.

    """
    if live is None:
        live = env.live

    if simple_path is not None:
        if s3_path is None:
            s3_uri = '{bucket}/{project_name}/{simple_path}'.format(
                simple_path=simple_path, bucket=bucket, project_name=env.project_name)
        else:
            s3_uri = '{bucket}/{s3_path}'.format(bucket=bucket, s3_path=s3_path)

        if local_path is None:
            local_path = simple_path

    elif s3_path and local_path:
        s3_uri = '{bucket}/{s3_path}'.format(bucket=bucket, s3_path=s3_path)
        local_path = local_path

    else:
        raise AttributeError('Must specify either simple path or both s3_path and local_path')

    up_template = 'cp {local_path} {s3_uri}'.format(
        local_path=local_path, s3_uri=s3_uri)

    down_template = 'cp {s3_uri} {local_path}'.format(
        local_path=local_path, s3_uri=s3_uri)

    s3(cmd=up_template if direction == 'up' else down_template, live=live)


@task
def docker_exec(service='postgres', cmd: str = 'bash', live: bool = None):
    """Function that wraps the docker exec interface.
    This task reduces the amount of boiler plate needed to execute tasks in docker containers
    spawned by docker-compose.


    Args:
        service: typically the name of the project with spaces, underscores, etc removed.
           E.g. project_name becomes projectname.
        cmd: The command to be executed in the docker container.
        live: live

    Returns:
        None

    """
    if live is None:
        live = env.live

    docker(cmd='exec -it {project_name}_{service}_1 {cmd}'.format(
        service=service, cmd=cmd, project_name=env.project_name), live=live)


@task
def loaddata(app: str = 'config', file_name='initial_data', extension: str = 'json'):
    """

    Args:
        app: which app
        file_name: Defaults to initial_data.
        extension: Default is json. Yaml is also supported if PyYaml is installed.

    Returns:

    """
    manage('migrate')
    path = 'src/' if not env.live else ''
    manage('loaddata {path}{app}/fixtures/{file_name}.{extension}'.format(**locals()))


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
            print(green('(dry) '), yellow('[localhost] '),
                  'scp {host}:{remote_path} {local_path}'.format(**locals()), sep='')

        def put(remote_path, local_path=None, use_sudo=False, temp_dir=""):
            if not isinstance(local_path, str):
                local_path = '"' + local_path.getvalue() + '"'
            host = env.host_string
            print(green('(dry) '),  yellow('[localhost] '),
                  'scp {local_path} {host}:{remote_path}'.format(**locals()), sep='')
