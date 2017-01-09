import logging
import os
import posixpath
from distutils.util import strtobool

from fabric.api import env, local, run, settings, put, prompt, task
from fabric.colors import green
from fabric.contrib.project import rsync_project

from dstack_tasks.utils import activate_venv
from dstack_tasks.wrappers import compose, manage, filer, postgres, execute


def fabric_setup() -> None:
    """Configure Fabric

    """
    # Global config
    env.use_ssh_config = True
    env.log_level = logging.INFO
    env.pwd = local("pwd", capture=True)


def local_setup(collection: str = '') -> None:
    """Configure local paths and settings

    Will also load .env files and <collection>.env files
    if python-dotenv is installed. <collection.env> files are stored in
    the project root under the .local folder and should not be checked into version control.

    Args:
        collection: The <collection>.env file that should be loaded before a task is executed.

    """
    # Local paths
    # env.project_path = os.path.dirname(os.path.dirname(__file__))
    env.local_dotenv_path = os.path.join(env.project_path, '.env')

    # Node config
    env.node_modules_prefix = 'bin'
    env.node_modules = os.path.join(
        env.project_path, env.node_modules_prefix, '/node_modules/.bin/')

    try:
        from dotenv import load_dotenv
    except ImportError:
        def load_dotenv(path: str = None):
            print('Did not load: ' + path)
            if env.log_level <= logging.INFO:
                print('Python-dotenv must be installed to load .env files:')
                print('pip install -U python-dotenv')

    # Read collection .env overrides
    if collection:
        load_dotenv(os.path.join(env.project_path, '.local', collection + '.env'))

    # Read local .env
    load_dotenv(env.local_dotenv_path)


def remote_setup(project_name: str) -> None:
    """ Configure the project paths based on project_name

    Args:
        project_name: The name of the project

    """

    # Configure paths
    path_config = {
        'build': '/srv/build',
        'apps': '/srv/apps',

        'volumes': {
            'postgres': {
                'data': '/var/lib/postgresql/data',
            }
        }
    }
    env.build_dir = path_config['build']
    env.project_dir = posixpath.join(path_config['apps'], project_name)
    env.server_dotenv_path = posixpath.join(env.project_dir, '.env')
    env.postgres_data = path_config['volumes']['postgres']['data']

    # Configure deployment
    env.virtual_host = os.environ.get('VIRTUAL_HOST', project_name)


@task
def e(collection: str = '', tag: str = 'latest') -> None:
    """Set environment

    Optionally run before other task to configure environment

    Task to set the tag during runtime.

    Args:
        collection: Used to specify a local collection of env settings.
            Useful when having different setups like staging/production/etc

        tag: The tag, preferably a SemVer version compatible string.

    Returns:
        The tag supplied

    Examples:
        fab e:tag=v1.0.0 echo  # outputs the env with updated tag

    """

    fabric_setup()

    # Read the project config defaults file
    with open("project.yml", 'r') as stream:
        try:
            import yaml
        except ImportError:
            yaml = 'Module not fount, pleas install Pyyaml'
        try:
            config = yaml.safe_load(stream)
            env.project_name = config['project']['name']
            env.virtual_env = config['development']['conda_environment']
            env.release_tag = config['project']['version']
            env.image_tag = config['project']['version']
            env.image_name = config['deployment']['docker_image_name']
            env.organisation = config['project']['organisation']
            env.git_repo = config['project']['git_repo']
            env.wheel_factory = config['wheel_factory']['hostname']

        except yaml.YAMLError as exc:
            print(exc)

    local_setup(collection=collection)
    # print(os.environ.get('PROJECT_NAME'))

    env.project_name = os.environ.get('PROJECT_NAME', env.project_name)
    env.virtual_env = os.environ.get('VIRTUAL_ENV', env.virtual_env)
    env.image_name = os.environ.get('IMAGE_NAME', env.image_name)
    env.image_tag = os.environ.get('RELEASE_TAG', env.image_tag)

    # env.image_tag = collection if collection else 'latest'

    # print(env.image_name, env.image_tag)

    activate_venv(env=env, style='conda', venv=env.virtual_env)
    remote_setup(env.project_name)

    # Server environment
    env.hosts = [os.environ.get('HOST_NAME', collection), ]

    env.tag = tag


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


def _restore_latest_postgres(live: bool = False):
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
    env.env_dir = env_dir
    execute('rsync -aPh ./{env_dir}/ {host_name}:/srv/apps/{project_name}/{env_dir}'.format(**env), live=False)


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
