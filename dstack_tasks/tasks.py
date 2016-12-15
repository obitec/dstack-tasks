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
    """ Configure Fabric

    """
    # Global config
    env.use_ssh_config = True
    env.log_level = logging.INFO


def local_setup(collection: str = '') -> None:
    """Configure local paths and settings

    Will also load .env files and <collection>.env files
    if python-dotenv is installed
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
        load_dotenv(os.path.join(env.project_path, collection + '.env'))

    # Read local .env
    load_dotenv(env.local_dotenv_path)


def remote_setup(project_name: str) -> None:
    """ Configure the project paths based on project_name

    :param project_name:
    :return:
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
def e(collection: str = '') -> None:
    """ Set environment
    Optionally run before other task to configure environment

    :param collection:
    :return:
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


def install_help():
    print('To install Python 3 Fabric, run:')
    print('pip install -U Fabric3')


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
    """
    DEPRECATED
    TODO: Develop proper method for version controled static files release
    :return:
    """
    rsync_project('/srv/htdocs/%s/' % env.project_name, './var/www/', exclude=('node_modules',))


def upload_config():
    """
    DEPRECATED
    TODO: Move virtualhost logic to dockergen template
    :return:
    """
    put('./etc/nginx-vhost.conf', '/srv/nginx/vhost.d/%s' % env.virtual_host)
    run("sed -i.bak 's/{{project_name}}/%s/g' '/srv/nginx/vhost.d/%s'" % (
        env.project_name.replace('.', '\.'), env.virtual_host))
    # try:
    #     put('./etc/certs/%s.key' % env.virtual_host, '/srv/certs/')
    #     put('./etc/certs/%s.crt' % env.virtual_host, '/srv/certs/')
    # except:
    #     print('No certs found')


def reset_local_postgres(live: bool = False):
    import time
    timestamp = int(time.time())
    postgres('backup', tag=str(timestamp))

    compose('stop postgres', live=live)
    compose('rm -v postgres db_data', live=live)
    compose('up -d postgres')


def restore_latest_postgres(live: bool = False):
    # TODO: Implement intelligent database restore
    pass


def postgres_everywhere():
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
            local(r'python bin\utils\hosts.py postgres --set %docker_host%')
        print(green('Successfully updated hosts file!'))


def datr(module: str = 'auth', target: str = 'local') -> None:
    """ Manage data
    :param module:
    :param target:

    Manually run this command:
        fab manage:'dumpdata -v 0 --indent 2 assessment > ./src/data_dump.json',live=1
        fab filer:get,src/data_dump.json
        fab postgr
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
def clean_unused_volumes():
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
    env.env_dir = env_dir
    execute('rsync -aPh ./{env_dir}/ {host_name}:/srv/apps/{project_name}/{env_dir}'.format(**env), live=False)


@task
def container_reset(backup: bool = True, data: bool = False, container: str = 'postgres'):
    """ Resets the container

    :param container:
    :param backup:
    :param data:
    :return:
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
