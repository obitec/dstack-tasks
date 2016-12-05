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


@task
def execute(cmd: str = '--help', path: str = None, live: bool = False, **kwargs):
    """ Wrapper for both local and remote tasks optionally setting the execution path.

    :param cmd:
    :param path:
    :param live:
    :return:
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
    """

    :param image_tag:
    :param cmd:
    :param path:
    :param live:
    :return:
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
    """

    :param path:
    :param cmd:
    :param live:
    :return:
    """
    if path is None:
        path = ''
        # path = env.get('project_dir', '')

    execute(cmd='docker {cmd}'.format(cmd=cmd), path=path, live=live)


@task
def manage(cmd: str = 'help', live: bool = False) -> None:
    """

    :param cmd:
    :param live:
    :return:
    """
    if live:
        # TODO: Make _staging geniric or apply to others as well
        compose('run --rm webapp bash -c "python manage.py {cmd}"'.format(cmd=cmd), live=True)
    else:
        with prefix(env.activate):
            local('python src/manage.py {cmd}'.format(cmd=cmd))


@task
def pip(cmd: str = '--help') -> None:
    """

    :param cmd:
    :return:
    """
    with prefix(env.activate):
        local('pip {cmd}'.format(cmd=cmd))


@task
def conda(cmd: str = '--help') -> None:
    """

    :param cmd:
    :return:
    """
    with prefix(env.activate):
        local('conda {cmd}'.format(cmd=cmd))


@task
def filer(cmd: str = 'get',
          local_path: str = None, remote_path: str = None,
          file: str = '.env', use_sudo: bool = False) -> None:
    """

    Specifying a remote_path or a local_path overrides the "file" parameter.

    :param remote_path:
    :param local_path:
    :param cmd:
    :param file:
    :param use_sudo:
    :return:
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
    """
    Task for backup and restore of database
    :param cmd:
    :param live:
    :param tag:
    :param sync_prompt:
    :return:
    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    backup_name = 'db_backup.{tag}.tar.gz'.format(tag=tag)
    backup_path = '.local/backups'

    backup_path = posixpath.join('/backup/', backup_name)
    actions = {
        'backup': 'tar -zcpf %s /data' % backup_path,
        'restore': 'bash -c "tar xpf %s && chmod -R 700 /data"' % backup_path,
    }

    # The assumption is that 'live' will always be on unix server
    if live:
        backup_to_path = posixpath.join(env.project_dir, backup_path)
    else:
        backup_to_path = os.path.join(env.project_path, backup_path)
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
                filer(cmd='put', file=os.path.join(backup_path, backup_name), use_sudo=True)

        if not live and cmd == 'restore':
            answer = prompt('Do you first want to download the backup?', default='no', )
            if answer == 'yes':
                filer(cmd='get', file=posixpath.join(backup_path, backup_name))

    compose('stop postgres', live=live)
    docker('run --rm {data} {backup} postgres:9.5 {cmd}'.format(**params), live=live)
    compose('start postgres', live=live)

    if live and cmd == 'backup':
        if sync_prompt:
            answer = prompt('Did you want to download backup?', default='no', )
            if answer == 'yes':
                filer(cmd='get', file=posixpath.join(backup_path, backup_name))


@task
def bower(component: str = 'rebuild') -> None:
    """

    :param component:
    :return:
    """
    if component != 'rebuild':
        local('bower install --save {0}'.format(component))

    local(os.path.join(env.node_modules, 'bower-requirejs') + ' -c src/static/js/config.js')
    local(os.path.join(env.node_modules, 'r.js') + ' -o src/static/js/build.js')

    manage('collectstatic --noinput -v1')


@task
def npm(package: str = 'install'):
    """

    :param package:
    :return:
    """
    if package == 'install':
        local('npm install --only=dev --prefix bin')
    else:
        local('npm install --save-dev {0} --prefix bin'.format(package))


@task
def git(cmd: str = '--help', path: str = None, live: bool = False):
    """

    :param path: Required only when git cloning for the first time.
    :param cmd:
    :param live:
    :return:
    """
    execute('git {cmd}'.format(cmd=cmd), live=live, path=path)


@task
def s3(cmd: str = 'help') -> None:
    """

    :param cmd:
    :return:
    """

    execute('aws s3 {cmd}'.format(**locals()))


@task
def docker_exec(service='postgres', cmd: str = 'bash', live: bool = False):
    """

    :param service:
    :param cmd:
    :param live:
    :return:
    """
    env.service = service
    env.cmd = cmd
    docker(cmd='exec -it {project_name}_{service}_1 {cmd}'.format(**env), live=live)


@task
def loaddata(live: bool = False, app: str = 'config', file_name='initial_data', extension: str = 'json'):
    """

    :param extension:
    :param file_name:
    :param app:
    :param live:
    :return:
    """
    manage('migrate', live=live)
    path = 'src/' if not live else ''
    manage('loaddata {path}{app}/fixtures/{file_name}.{extension}'.format(**locals()), live=live)



@task
def dry(dry_run: bool = True) -> None:
    """Show, but don't run fabric commands"""
    global local, run, get, put

    if dry_run:
        # Redefine the local and run functions to simply output the command
        def local(command, capture=False, shell=None):
            print(green('(dry) '), yellow('[localhost] '), 'cd %s && ' % env.pwd if env.pwd else '', '%s' % command, sep='')

        def run(command, shell=True, pty=True, combine_stderr=None, quiet=False,
                warn_only=False, stdout=None, stderr=None, timeout=None, shell_escape=None,
                capture_buffer_size=None):
            print(green('(dry) '), red('[%s] ' % env.host_string), 'cd %s && ' % env.pwd if env.pwd else '', '%s' % command, sep='')

        def get(remote_path, local_path=None, use_sudo=False, temp_dir=""):
            host = env.host_string
            print(green('(dry) '), red('[{}] '.format(host)),
                  'scp {host}:{remote_path} {local_path}'.format(**locals()), sep='')

        def put(remote_path, local_path=None, use_sudo=False, temp_dir=""):
            host = env.host_string
            print(green('(dry) '), red('[{}] '.format(host)),
                  'scp {local_path} {host}:{remote_path}'.format(**locals()), sep='')
