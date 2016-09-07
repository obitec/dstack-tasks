import logging
import os
import posixpath
from pathlib import Path

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
def execute(cmd: str = '--help', path: str = None, live: bool = False):
    """

    :param cmd:
    :param path:
    :param live:
    :return:
    """
    if path is None:
        path = env.project_dir if live else ''
    print(path)
    with cd(path):
        run(cmd) if live else local(cmd)


@task
def compose(cmd: str = '--help', path: str = None, live: bool = False) -> None:
    """

    :param cmd:
    :param path:
    :param live:
    :return:
    """
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
def docker(cmd: str = '--help', live: bool = False) -> None:
    """

    :param cmd:
    :param live:
    :return:
    """
    execute(cmd='docker {cmd}'.format(cmd=cmd), path=env.get('project_dir', ''), live=live)


@task
def manage(cmd: str = 'help', live: bool = False) -> None:
    """

    :param cmd:
    :param live:
    :return:
    """
    if live:
        # TODO: Make _staging geniric or apply to others as well
        compose('run --rm webapp_staging bash -c "python manage.py {cmd}"'.format(cmd=cmd), live=True)
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
def filer(cmd: str = 'get', file: str = '.envs', use_sudo: bool = False) -> None:
    """

    :param cmd:
    :param file:
    :param use_sudo:
    :return:
    """
    if cmd == 'get':
        get(posixpath.join(env.project_dir, file), file)
    elif cmd == 'put':
        put(file, posixpath.join(env.project_dir, file), use_sudo=use_sudo)
        run('chmod go+r {0}'.format(posixpath.join(env.project_dir, file)))


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
        'data': '-v %s_dbdata:/data' % env.project_name.replace('.', ''),
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
    docker('run --rm {data} {backup} postgres {cmd}'.format(**params), live=live)
    compose('start postgres', live=live)

    if live and cmd == 'backup':
        if sync_prompt:
            answer = prompt('Did you want to download backup?', default='no', )
            if answer == 'yes':
                filer(cmd='get', file=posixpath.join('var/backups/', backup_name))


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
def git(cmd: str = '--help', live: bool = False):
    """

    :param cmd:
    :param live:
    :return:
    """
    execute('git {cmd}'.format(cmd=cmd), live=live)


@task
def s3(cmd: str = 'help') -> None:
    """

    :param cmd:
    :return:
    """

    execute('aws s3 {cmd}'.format(**locals()))

