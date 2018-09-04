import os
import time
from datetime import datetime

from dotenv import set_key
from invoke import task
from setuptools_scm import get_version

from .base import LOCAL_PREFIX, REMOTE_PREFIX, do, env
from .notify import send_alert
from .wrap import compose, docker, git, python, s3cmd


@task
def test(ctx, cmd='uname -a', path='.'):
    do(ctx, cmd=cmd, path=path, env={'foo': 'bar'})


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

    if static:
        excludes = '--exclude=' + ' --exclude='.join(['"*.less"', '"*.md"', '"ckeditor/"'])
        do(ctx, f'webpack', path='src/assets/')
        python(ctx, f'./src/manage.py collectstatic --no-input -v0', conda_env=True)
        # do(ctx, f'rm -rf .local/static/ckeditor/')
        if upload:
            do(ctx, f'tar -zcvf .local/static_v{version}.tar.gz {excludes} -C .local/static/ .')
            s3cmd(ctx, local_path=f'.local/static_v{version}.tar.gz', s3_path=f'{project_name}/static/')


@task
def deploy_code(ctx, version, download=True, build=True, static=False, migrate=False, project=None, bucket=None):
    project = project or ctx['project_name']
    bucket = bucket or ctx['bucket_name']

    # TODO: make configurable
    stack_path = 'stack/django/'
    local_path = '.local/'

    if getattr(ctx, 'host', False):
        stack_path = os.path.abspath(os.path.join(ctx.dir, stack_path))
        local_path = os.path.abspath(os.path.join(ctx.dir, local_path))

    # Update the env files
    do(ctx, f'sed -i.bak "s/^VERSION=.*/VERSION={version}/g" {os.path.join(ctx.dir, ".env")}')
    do(ctx, f'sed -i.bak "s/^VERSION=.*/VERSION={version}/g" {os.path.join(stack_path, ".env")}')

    do(ctx, f'aws s3 cp --quiet s3://{bucket}/{project}/dist/{project}-{version}-py3-none-any.whl {stack_path}')
    if static:
        if download:
            do(ctx, f'aws s3 cp --quiet s3://{bucket}/{project}/static/static_v{version}.tar.gz {local_path}')
        do(ctx, f'tar -zvxf static_v{version}.tar.gz -C static/', path=local_path)
        do(ctx, f'find {local_path}static/ -type d -exec chmod 755 {{}} \\;')
        do(ctx, f'find {local_path}static/ -type f -exec chmod 644 {{}} \\;')

    if build:
        del os.environ['VERSION']
        compose(ctx, cmd='build django')
        compose(ctx, cmd='up -d django')
        compose(ctx, cmd='up -d celery_worker celery_camera')

    if migrate:
        db(ctx, 'backup', upload=True)
        compose(ctx, cmd=f'exec django {project} migrate')


@task
def docker_ps(ctx):
    """

    :return: List of running container names
    """
    result = docker(ctx, cmd='ps -a --format "table {{.Names}}"', hide=True)
    containers = result.stdout.split('\n')[1:-1]
    print(containers)
    return containers


# TODO: local_build for building docker image locally

@task
def release_superset(ctx, version):
    # TODO: make variable
    project = ctx['project_name']
    project_root = f'../{project}'
    bucket_name = ctx['S3_BUCKET_NAME']

    do(ctx, 'rm -rf superset/assets/dist/*')
    do(ctx, 'yarn run build', path='superset/assets/')
    do(ctx, 'rm -rf build/*')
    do(ctx, 'python setup.py bdist_wheel')
    do(ctx, f'aws s3 cp --quiet dist/superset-{version}-py3-none-any.whl s3://{bucket_name}/superset/dist/')
    do(ctx, f'cp ./dist/superset-{version}-py3-none-any.whl {project_root}/tests/stack/superset/')

    # TODO: wrap set_key in function
    if not env.dry_run:
        # dotenv -f .env -q auto set VERSION version
        set_key(
            dotenv_path=f'{project_root}/.env', key_to_set='SUPERSET_VERSION', value_to_set=version, quote_mode='auto')
    else:
        print(REMOTE_PREFIX if ctx.get('host', False) else LOCAL_PREFIX,
              f'dotenv -f {project_root}/.env -q auto set SUPERSET_VERSION {version}')

    compose(ctx, 'build superset', path=f'{project_root}')


def now_tag(tag=None):
    time_str = datetime.utcnow().replace(microsecond=0).isoformat().replace(':', '-') + 'Z'
    return f'{time_str}_{tag}' if tag else time_str


@task
def db(ctx, cmd, tag=None, upload=True, notify=False, replica=True, project=None, image='postgres:9.5',
       service_main='postgres', volume_main='postgres',
       service_standby='postgres-replica', volume_standby='dbdata', data_dir=None):
    """

    Args:
        ctx:
        cmd:
        tag:
        upload: Default=True. Whether to upload to s3 or not
        notify: Default=True. Whether to post machine_status
        replica: Whether to use simple backup/restore or backup/restore with replica
        project:
        image:
        service_main:
        volume_main:
        service_standby:
        volume_standby:
        data_dir: The storage location for backups, static, media files.

    Returns:

    """
    if project is None:
        project = ctx['project_name']

    if data_dir is None:
        data_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.getenv('COMPOSE_FILE')), os.getenv('LOCAL_DIR')))
    backup_path = os.path.join(ctx['dir'], f'{data_dir}/backups')
    # promote_cmd = 'su - postgres -c "/usr/lib/postgresql/9.5/bin/pg_ctl promote -D /var/lib/postgresql/data"'
    if cmd == 'backup':
        tag = now_tag(tag)
        backup_cmd = f'tar -zcpf /backup/db_backup.{tag}.tar.gz /data'
        # Stop container and make backup of ${PGDATA}
        psql(ctx, sql=f"INSERT INTO backup_log (tag) VALUES ('{tag}');")
        service = service_standby if replica else service_main
        volume = volume_standby if replica else volume_main
        compose(ctx, f'stop {service}')
        docker(ctx, f'run --rm -v {project}_{volume}:/data -v {backup_path}:/backup {image} {backup_cmd}')
        compose(ctx, f'start {service}')
        if upload:
            s3cmd(ctx, local_path=os.path.join(backup_path, f'db_backup.{tag}.tar.gz'), s3_path=f'{project}/backups/')
        if replica:
            result = psql(ctx, sql=f"SELECT * from backup_log WHERE tag='{tag}'", service=service)
            if tag in getattr(result, 'stdout', ''):
                print('Success!')
        if notify:
            message = f'Backup with tag={tag} uploaded to S3. Please verify.'
            send_alert(ctx, message)

    elif cmd == 'restore':
        restore_cmd = f'bash -c "tar xpf /backup/db_backup.{tag}.tar.gz && chmod -R 700 /data"'
        # TODO: First restart django with updated POSTGRES_HOST=standby and then only destroy afterwards
        if replica:
            # Destroy replica server and associated volume
            compose(ctx, f'rm -vsf {service_standby}')
            docker(ctx, f'volume rm {project}_{volume_standby}', warn=True)
        # Restore database
        compose(ctx, f'-p {project} stop {service_main}')
        docker(ctx, f'run --rm -v {project}_{volume_main}:/data -v {backup_path}:/backup {image} {restore_cmd}')
        compose(ctx, f'-p {project} start {service_main}')
        # compose(ctx, f'exec -T {service_main} {promote_cmd}')
        if replica:
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
    elif cmd == 'enable-replication':
        # TODO: Test this code and maybe make part of main restore task
        compose(ctx, f'exec {service_main} ./docker-entrypoint-initdb.d/10-config.sh')
        compose(ctx, f'exec {service_main} ./docker-entrypoint-initdb.d/20-replication.sh')
        compose(ctx, f'restart {service_main}')
        compose(ctx, f'up -d {service_standby}')


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


@task
def create_backup_table(ctx):
    sql = """CREATE TABLE IF NOT EXISTS backup_log (
                id serial not null primary key,
                date_created timestamp default current_timestamp,
                tag VARCHAR(255))"""
    psql(ctx, sql=" ".join(sql.split()))
    psql(ctx, sql="INSERT INTO backup_log (tag) VALUES ('initialized');")
