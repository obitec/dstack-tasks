import logging
import os
import posixpath
from distutils.util import strtobool
from os import getenv

from dotenv import load_dotenv
from fabric.api import env, local, prompt, put, run, settings, task
from fabric.colors import green
from fabric.contrib.project import rsync_project
from setuptools_scm import get_version

from dstack_tasks.wrappers import compose, execute, filer, manage, postgres

# Global config
env.use_ssh_config = True
env.log_level = logging.INFO
# env.pwd = local("pwd", capture=True)
env.pwd = os.getcwd()
env.src = os.path.join(env.pwd, 'src')
env.dir = os.path.basename(env.pwd)
env.live = False
env.dry = False

# Attempt to get a version number
try:
    # env.version = get_version(root='.', relative_to=env.pwd)
    env.version = get_version()
except LookupError:
    try:
        with open(os.path.join(env.src, 'version.txt')) as f:
            env.version = f.readline().strip()
    except FileNotFoundError:
        env.version = getenv('VERSION', '0.0.0-dev')

env.tag = env.version


def remote_setup(hostname: str = None) -> None:
    """ Configures the project paths based on project_name

    Args:
        hostname: The name of the host as defined in .ssh/config

    """

    # Configure paths
    path_config = {
        'build': '/srv/build',
        'apps': '/srv/apps',

        'volumes': {
            'postgres_data': '/var/lib/postgresql/data',
        }
    }
    env.build_dir = path_config['build']
    env.project_dir = posixpath.join(path_config['apps'], env.project_name)
    env.server_dotenv_path = posixpath.join(env.project_dir, '.env')
    env.postgres_data = path_config['volumes']['postgres_data']

    # Configure deployment
    env.virtual_host = getenv('VIRTUAL_HOST', env.project_name)

    # Try to get the host_name
    env.hosts = [getenv('HOST_NAME', hostname), ]


@task
def e(collection: str = None, tag: str = None, live: bool = False) -> None:
    """Set environment

    Optionally run before other task to configure environment

    Task to set the tag during runtime.

    Args:
        collection: Used to specify a local collection of env settings.
            Useful when having different setups like staging/production/etc
        tag: The tag, preferably a SemVer version compatible string.
        live: Whether to run the command locally or on the server

    Returns:
        The tag supplied

    Examples:
        fab e:tag=v1.0.0 echo  # outputs the env with updated tag

    Configure local paths and settings

    Will also load .env files and <collection>.env files
    if python-dotenv is installed. <collection.env> files are stored in
    the project root under the .local folder and should not be checked into version control.

    Args:
        collection: The <collection>.env file that should be loaded before a task is executed.

    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    # Read collection.env overrides and then main local .env
    # because load_dotenv does not override env variables
    env.local_dotenv_path = os.path.join(env.pwd, '.env')
    if collection:
        load_dotenv(os.path.join(env.pwd, '.local', collection + '.env'))
    load_dotenv(env.local_dotenv_path)

    env.update({
        'tag': tag or env.tag,  # Allows working with a specific version to e.g. backup a database
        'live': live,
        'src': getenv('SOURCE_DIR', env.src),

        'project_name': getenv('PROJECT_NAME', env.dir),
        'organisation': getenv('ORGANISATION', ''),
        'git_repo': getenv('GIT_REPO', ''),
        'venv_name': getenv('VENV_NAME', ''),
        'venv_type': getenv('VENV_TYPE', 'conda'),
        'image_name': getenv('IMAGE_NAME', ''),

        'node_modules_prefix': getenv('NODE_PREFIX', '.local'),
    })

    if not env.image_name:
        env.image_name = env.organisation + '/' + env.dir

    # Guess the virtual env
    env.venv_name = env.venv_name or env.project_name if env.venv_type == 'conda' else 'venv'

    # path to node modules
    env.node_modules = os.path.join(env.pwd, env.node_modules_prefix, '/node_modules/.bin/')

    # template for activating the python virtual environment
    activate = {
        'conda': {
            'posix': 'source activate {venv}',  # $ source activate <venv>
            'nt': 'activate {venv}'  # C:\> activate <venv>
        },
        'pip': {
            'posix': 'source {venv}/bin/activate',  # $ source <venv>/bin/activate
            'nt': r'{venv}\Scripts\activate.bat',  # C:\> <venv>\\Scripts\\activate.bat
            # PS C:\> <venv>\\Scripts\\Activate.ps1
        }
    }
    env.activate = activate[env.venv_type][os.name].format(venv=env.venv_name)

    # Setup specific to remote server
    remote_setup(collection)


def translate():
    manage('makemessages -l af')
    manage('compilemessages')


def backup_basics():
    manage('dumpdata --indent=2 '
           'flatpages sites auth.users auth.groups > '
           'src/config/fixtures/initial_data.json')


def sqlite_reset():
    local("echo $PROJECT_NAME")
    local("mv ./src/db.sqlite3 ./src/db.sqlite3.bak")
    local('find . -path "*/migrations/*.py" -not -name "__init__.py" -delete')
    manage('makemigrations')
    manage('migrate')
    manage('collectstatic --noinput -v1')
    manage('loaddata ./src/config/fixtures/initial_data.json')
    # manage('loaddata ./src/customer_management/fixtures/initial_data.json')


def upload_www():
    """ **Deprecated**. See :py:func:`deploy_runtime`.

    """
    # TODO: Develop proper method for version controlled static files release
    rsync_project('/srv/htdocs/%s/' % env.project_name, './var/www/', exclude=('node_modules',))


def upload_config():
    """ **Deprecated**. See :py:func:`deploy_runtime`.

    """
    # TODO: Move virtualhost logic to dockergen template

    put('./etc/nginx-vhost.conf', '/srv/nginx/vhost.d/%s' % env.virtual_host)
    run("sed -i.bak 's/{{project_name}}/%s/g' '/srv/nginx/vhost.d/%s'" % (
        env.project_name.replace('.', '\.'), env.virtual_host))
    # try:
    #     put('./etc/certs/%s.key' % env.virtual_host, '/srv/certs/')
    #     put('./etc/certs/%s.crt' % env.virtual_host, '/srv/certs/')
    # except:
    #     print('No certs found')


def _reset_local_postgres(live: bool = False):
    import time
    timestamp = int(time.time())
    postgres('backup', tag=str(timestamp))

    compose('stop postgres', live=live)
    compose('rm -v postgres db_data', live=live)
    compose('up -d postgres')


def _restore_latest_postgres():
    # TODO: Implement intelligent database restore
    pass


@task
def configure_hosts():
    """Sets up hosts file to allow seamless local development that mimics production environment.

    Returns:
        None

    Warning:
        Experimental!

    Todo:
        Properly document and link
        sudo ifconfig lo0 alias 10.200.10.1/24

    """
    # TODO: Update for Docker for Mac.

    ip_template = 'docker inspect {0}_postgres_1 | jq .[0].NetworkSettings.Networks.{0}_internal.IPAddress'
    ip_address = local(ip_template.format(env.project_name), capture=True).strip('"')

    if env.os == 'posix':
        local('sudo sed -i "" "/[[:space:]]postgres$/d" /etc/hosts')
        local('sudo /bin/bash -c "echo {ip_address}    postgres >> /etc/hosts"'.format(ip_address=ip_address))

        # local('echo ${DOCKER_HOST}')
        # local('sudo /bin/bash -c "echo $(echo ${DOCKER_HOST} | '
        #       'grep -oE \'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\')    postgres >> /etc/hosts"')

    else:
        with settings(warn_only=True):
            local(r'python -m dstack_tasks._hosts postgres --set %docker_host%')
        print(green('Successfully updated hosts file!'))


def datr(module: str = 'auth', target: str = 'local') -> None:
    """Transport data to and from development and production servers

    Warning:
        This task has only been tested for NaturalData models with less than 100 entries,
        it might not be suitable for complex models and large datasets.

    Args:
        module: The module to transport
        target: If local, data is dumped from server and installed on local machine,
            else it is dumped from local machine and uploaded to server

    Examples:
        fab manage:'dumpdata -v 0 --indent 2 assessment > ./src/data_dump.json',live=True
        fab filer:get,src/data_dump.json
        fab postgres:backup,live=False
        fab manage:'loaddata ./src/dump_data.json'
    """

    if target == 'remote':
        manage('dumpdata -v 0 --indent 2 --natural-foreign {module} > ./src/data_dump.json'.format(
            module=module), live=False)
        filer('put', 'src/data_dump.json')
        postgres('backup', live=True)
        manage('loaddata data_dump.json', live=True)

    elif target == 'local':
        manage('dumpdata -v 0 --indent 2 --natural-foreign {module} > /app/data_dump.json'.format(
            module=module), live=True)
        filer('get', 'src/data_dump.json')
        answer = prompt('Do you want to install data locally?', default='no', )
        if answer == 'yes':
            # postgres('backup', live=False)
            manage('loaddata ./src/data_dump.json', live=False)
    else:
        print('Invalid option. Target must be local or remote')


# DANGER!!!
def _clean_unused_volumes():
    with settings(warn_only=True):
        run('docker rm -v  $(docker ps --no-trunc -aq status=exited)')
        run('docker rmi $(docker images -q -f "dangling=true")')

        # TODO: Check if up to date before releasing
        # run('docker run --rm'
        #     '-v /var/run/docker.sock:/var/run/docker.sock '
        #     '-v /var/lib/docker:/var/lib/docker '
        #     'martin/docker-cleanup-volumes')


@task
def sync_env(env_dir: str = '.local'):
    """rsync .env files to server.

    Args:
        env_dir: .local by default.

    """
    env.live = False
    env.env_dir = env_dir
    execute('rsync -aPh ./{env_dir}/ {host_name}:/srv/apps/{project_name}/{env_dir}'.format(**env))


@task
def container_reset(backup: bool = True, data: bool = False, container: str = 'postgres'):
    """ Resets the docker container, also removes dangling volumes.

    Warning:
        Removes dangling data volumes, will result in dataloss!

    Args:
        backup: To backup or not to backup postgres database first.
        data: If True, stop and delete the container along with any dangling volumes, else just forces a recreate.
            If a named volume is involved, that volume needs to be manually deleted using docker volume rm <name>.
            But always first backup this volume!!
        container: Container name as given in the docker-compose file.

    Returns:
        None
    """

    if backup and bool(strtobool(backup)):
        postgres(cmd='backup')

    if data and bool(strtobool(data)):
        compose('stop ' + container)
        compose('rm -v ' + container)
        # docker('volume rm gauseng_dbdata')
        compose('up -d ' + container)
    else:
        compose('up -d --force-recreate ' + container)
