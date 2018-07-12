import os
import time
from datetime import datetime

import colorama
from dotenv import set_key
from invoke import task
from setuptools_scm import get_version

from .base import do, env
from .wrap import compose, docker, git, postgres, python, s3cmd


@task
def test(ctx, cmd='uname -a', path='.'):
    do(ctx, cmd=cmd, path=path, env={'foo': 'bar'})


@task
def deploy(ctx, project_name=None, version='0.0.0', service='django',
           run_service=True, migrate=False, static=False, backup=False, interactive=False):
    """Download wheel from s3cmd, set .env variables, build project and up it.

    Args:
        ctx:
        run_service: Default = True. Runs the service after building it.
        service: The docker compose service as specified in the compose file. E.g. 'django'.
        project_name: The name of the python package. If None, uses directory name with '_' replacing '-'.
        version: The python package version to deploy.
        migrate: If True, migrates the database.
        static: Default = False. If True, also updates static files.
        backup:
        interactive:

    Returns: Project status

    """

    project_name = project_name or os.path.basename(os.getcwd()).replace('-', '_')

    extends = ['django', 'celery_worker', 'celery_beat', 'notebook']
    base_service = service if service not in extends else '_webapp'

    # aws s3cmd cp s3cmd://dstack-storage/toolset/deploy/toolset-0.16.18-py3-none-any.whl ./
    s3cmd(ctx,
          s3_path=f'{project_name}/dist/{project_name}-{version}-py3-none-any.whl',
          local_path=f'stack/{base_service}/',
          direction='down',
          project_name=project_name)
    # substitute django service for webapp

    if not env.dry_run:
        # dotenv -f .env -q auto set VERSION version
        set_key(dotenv_path='.env', key_to_set='VERSION', value_to_set=version, quote_mode='auto')
        # dotenv -f .local/webapp.env -q auto set VERSION version
        set_key(dotenv_path=f'./stack/{base_service}/.env',
                key_to_set='RELEASE_TAG', value_to_set=version, quote_mode='auto')
    else:
        print(f'dotenv -f .env -q auto set VERSION {version}')
        print(f'dotenv -f stack/{base_service}/.env -q auto set RELEASE_TAG {version}')

    # docker-compose build webapp
    compose(ctx, cmd=f'build {base_service}', path=f'/srv/apps/{project_name}/')

    if run_service:
        # docker-compose up -d django
        compose(ctx, cmd=f'up -d {service}')

    # docker-compose run --rm webapp dstack migrate
    if migrate:
        if interactive:
            answer = input('Do you want to backup postgres')
            if answer in ['yes', 'y', 'Yes']:
                url_timestamp = str(int(datetime.now().timestamp() * 1000))
                postgres(ctx, cmd='backup', tag=url_timestamp)
        compose(ctx, cmd=f'exec django toolset migrate')

    if static:
        # TODO: Until proper static file approach is implemented, use latest to reduce bandwidth usage
        version = 'latest'
        # basically, aws sync from dstack to .local/static is the current preferred way.
        s3cmd(ctx, cmd='sync --exact-timestamps', direction='down',
              simple_path='.local/static/', s3_path=f'{project_name}/static/{version}/')

    return None


# TODO: See what invoke did in their release task that requires a specific branch
@task
def release_code(ctx, project_name=None, version=None, upload=True, push=False, static=True, build=True):
    """Tag, build and optionally push and upload new project release

    """
    # TODO set project name in ctx
    project_name = project_name or os.path.basename(os.getcwd()).replace('-', '_')
    scm_version = get_version()
    version = version or '.'.join(scm_version.split('.')[:3])

    if build:
        print(f'Git version: {scm_version}')
        if len(scm_version.split('.')) > 4:
            print('First commit all changes, then run this task again')
            return False

        if scm_version != version:
            git(ctx, f'tag v{version}')

        # Clean and build
        do(ctx, cmd='rm -rf build/')
        python(ctx, cmd='setup.py bdist_wheel', conda_env=True)

    if push:
        git(ctx, f'push origin v{version}')

    if upload:
        s3cmd(ctx,
              simple_path=f'dist/{project_name}-{version}-py3-none-any.whl', direction='up', project_name=project_name)

    # aws s3 sync ./.local/static/ s3://dstack-storage/toolset/static/v1/
    if static:
        # ignore = ['test', 'docs', '*.md', '*.txt', '*.sass', '*.less', '*.html', 'LICENSE', '*.coffee']
        # ignore_params = ' -i '.join(ignore)
        #
        # python(ctx, cmd=f'./src/manage.py collectstatic -v0 -i {ignore_params}', conda_env=True)
        # --exact-timestamps
        # s3cmd(ctx, cmd='sync', local_path='./.local/static/', s3_path=f'static/v0.18.10/', exact_timestamps=True)
        # TODO: Once webpack has been integrated, use version tag instead of `latest`
        # s3cmd(ctx, cmd='sync', local_path='./.local/static/', s3_path=f'{project_name}/static/latest/',
        #       exact_timestamps=True)

        excludes = '--exclude=' + ' --exclude='.join(['"*.less"', '"*.md"', '"ckeditor/"'])
        do(ctx, f'webpack', path='src/assets/')
        python(ctx, f'./src/manage.py collectstatic --no-input -v0', conda_env=True)
        # do(ctx, f'rm -rf .local/static/ckeditor/')
        do(ctx, f'tar -zcvf .local/static_v{version}.tar.gz {excludes} -C .local/static/ .')
        # do(ctx, f'tar -zcvf .local/static_v{version}.tar.gz .local/static/')
        s3cmd(ctx, local_path=f'.local/static_v{version}.tar.gz',  s3_path='toolset/static/')


@task
def docker_ps(ctx):
    """

    :return: List of running container names
    """
    result = docker(ctx, cmd='ps -a --format "table {{.Names}}"', hide=True)
    containers = result.stdout.split('\n')[1:-1]
    print(containers)
    return containers


@task
def update(ctx):
    s3cmd(ctx, direction='down', local_path='tasks.py', s3_path='plant_secure/stack/tasks.py')


@task
def run_test(ctx):
    compose(ctx, cmd='build webapp')
    compose(ctx, cmd='build superset')
    compose(ctx, cmd='up -d django')
    compose(ctx, cmd='up -d superset')
    compose(ctx, cmd='up -d nginx-local')


@task
def release_superset(ctx, version='0.25.6b1'):
    # TODO: make variable
    dev_root = '/Users/canary/Development/'
    bucket_name = 'dstack-storage'

    do(ctx, 'rm -rf superset/assets/dist/*')
    do(ctx, 'yarn run build', path='superset/assets/')
    do(ctx, 'rm -rf build/*')
    do(ctx, 'python setup.py bdist_wheel')
    do(ctx, f'aws s3 cp dist/superset-{version}-py3-none-any.whl s3://{bucket_name}/superset/dist/')
    do(ctx, f'cp ./dist/superset-{version}-py3-none-any.whl ../toolset/tests/stack/superset/')

    # TODO: wrap set_key in function
    if not env.dry_run:
        # dotenv -f .env -q auto set VERSION version
        set_key(dotenv_path='../toolset/.env', key_to_set='SUPERSET_VERSION', value_to_set=version, quote_mode='auto')
    else:
        print(colorama.Fore.YELLOW + '[local]' + colorama.Fore.RESET,
              f'dotenv -f ../toolset/.env -q auto set SUPERSET_VERSION {version}')

    compose(ctx, 'build superset', path=f'{dev_root}/toolset')


@task
def local_build(ctx):
    python(ctx, 'setup.py bdist_wheel', conda_env=True)
    version = get_version()
    print(version)
    do(ctx, f'cp '
            f'dist/toolset-{version}-py3-none-any.whl '
            f'tests/stack/_webapp/toolset-2.0.1-py3-none-any.whl')
    compose(ctx, cmd='build django')
    compose(ctx, cmd='up -d django')


def now_tag(tag=None):
    time_str = datetime.utcnow().replace(microsecond=0).isoformat().replace(':', '-') + 'Z'
    return f'{time_str}_{tag}' if tag else time_str


@task
def db(ctx, cmd, tag=None, upload=True, project='toolset', image='postgres:9.5',
       service_main='postgres', volume_main='postgres',
       service_standby='postgres-replica', volume_standby='dbdata'):
    """

    Args:
        ctx:
        cmd:
        tag:
        upload: Default=True. Whether to upload to s3 or not
        project:
        image:
        service_main:
        volume_main:
        service_standby:
        volume_standby:

    Returns:

    """
    backup_path = os.path.join(ctx['dir'], '.local/backups')
    promote_cmd = 'su - postgres -c "/usr/lib/postgresql/9.5/bin/pg_ctl promote -D /var/lib/postgresql/data"'
    if cmd == 'backup':
        tag = now_tag(tag)
        backup_cmd = f'tar -zcpf /backup/db_backup.{tag}.tar.gz /data'
        # Stop container and make backup of ${PGDATA}
        psql(ctx, sql=f"INSERT INTO backup_log (tag) VALUES ('{tag}');")
        compose(ctx, f'stop {service_standby}')
        docker(ctx, f'run --rm -v {project}_{volume_standby}:/data -v {backup_path}:/backup {image} {backup_cmd}')
        compose(ctx, f'start {service_standby}')
        if upload:
            s3cmd(ctx, local_path=os.path.join(backup_path, f'db_backup.{tag}.tar.gz'), s3_path=f'{project}/backups/')
        result = psql(ctx, sql=f"SELECT * from backup_log WHERE tag='{tag}'", service='postgres-replica')
        if tag in getattr(result, 'stdout', ''):
            print('Success!')
    elif cmd == 'restore':
        restore_cmd = f'bash -c "tar xpf /backup/db_backup.{tag}.tar.gz && chmod -R 700 /data"'
        # TODO: First restart django with updated POSTGRES_HOST=standby and then only destroy afterwards
        # Destroy replica server and associated volume
        compose(ctx, f'rm -vsf {service_standby}')
        docker(ctx, f'volume rm {project}_{volume_standby}')
        # Restore database
        compose(ctx, f'stop {service_main}')
        docker(ctx, f'run --rm -v {project}_{volume_main}:/data -v {backup_path}:/backup {image} {restore_cmd}')
        compose(ctx, f'start {service_main}')
        # compose(ctx, f'exec -T {service_main} {promote_cmd}')
        compose(ctx, f'exec -T {service_main} touch /tmp/pg_failover_trigger')
        # Recreate standby database
        compose(ctx, f'up -d {service_standby}')
    elif cmd == 'recreate-standby':
        compose(ctx, f'rm -vsf {service_standby}')
        docker(ctx, f'volume rm {project}_{volume_standby}')
        compose(ctx, f'up -d {service_standby}')
    elif cmd == 'check':
        result_main = psql(ctx, 'SELECT * from backup_log;')
        result_standby = psql(ctx, 'SELECT * from backup_log;', service='postgres-replica')
        if ('initialized' in getattr(result_main, 'stdout', '') and
                'initialized' in getattr(result_standby, 'stdout', '')):
            print('Success!')


@task
def psql(ctx, sql, service='postgres', user='postgres'):
    return compose(ctx, f'exec -T {service} psql -U {user} -c "{sql}"')


@task
def full_db_test(ctx):
    db(ctx, cmd='backup', upload=False)
    psql(ctx, sql=f"INSERT INTO backup_log (tag) VALUES ('not_backed_up'); SELECT * from backup_log;")
    tag = input("Tag:")
    db(ctx, cmd='restore', tag=tag)
    time.sleep(10)
    db(ctx, cmd='check')


#     CREATE TABLE replication_test (a INT, b INT, c VARCHAR(255));
# INSERT INTO replication_test VALUES (1, 2, 'it works');
#
#
# docker-compose exec postgres-replica psql -U postgres
#
# SELECT c from replication_test;


@task
def create_backup_table(ctx):
    sql = """CREATE TABLE IF NOT EXISTS backup_log (
                id serial not null primary key,
                date_created timestamp default current_timestamp,
                tag VARCHAR(255))"""
    psql(ctx, sql=" ".join(sql.split()))
    psql(ctx, sql="INSERT INTO backup_log (tag) VALUES ('initialized');")
