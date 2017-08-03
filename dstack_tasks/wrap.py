import os
import sys

import boto3
from invoke import task

from .base import do, env


@task
def bash(ctx, cmd, path=None, local=None, env_vars=None, host=None):
    """

    Args:
        ctx:
        cmd:
        path:
        local:
        env_vars:
        host:

    Returns:

    """
    if env_vars:
        env_vars = dict(item.split("=") for item in env_vars.split(","))

    return do(ctx, cmd=cmd, path=path, local=local, env=env_vars, host=host)


@task
def docker(ctx, cmd='--help', **kwargs):
    """System docker wrapper.

    Args:
        ctx:
        cmd:
        **kwargs:

    Returns:

    """
    return do(ctx, f'docker {cmd}', **kwargs)


@task
def compose(ctx, cmd='--help', **kwargs):
    """System compose wrapper.

    Args:
        ctx:
        cmd:
        **kwargs:

    Returns:

    """
    return do(ctx, f'docker-compose {cmd}', **kwargs)


@task
def git(ctx, cmd='--help', **kwargs):
    """System git wrapper.

    Args:
        ctx:
        cmd:
        **kwargs:

    Returns:

    """
    return do(ctx, f'git {cmd}', **kwargs)


@task
def python(ctx, cmd='--help', venv=True, conda_env=False, **kwargs):
    """System python wrapper with venv activation.

    Args:
        ctx:
        cmd:
        venv:
        conda_env:
        **kwargs:

    Returns:

    """
    # TODO: Auto-detect venv type? Or at least better switching

    if conda_env:
        python_path = f'{ctx.activate} && python'
    elif venv:
        python_path = f'{ctx.activate} && python'
    else:
        python_path = 'python'

    return do(ctx, f'{python_path} {cmd}', **kwargs)


@task
def pip(ctx, cmd='list', venv=True, **kwargs):
    """System pip wrapper.

    Args:
        ctx:
        cmd:
        venv:
        **kwargs:

    Returns:

    """
    return python(ctx, cmd=f'-m pip {cmd}', venv=venv, **kwargs)


@task
def s3cmd(ctx, cmd='cp', simple_path=None, direction='up', local_path=None, s3_path=None, bucket='s3://dstack-storage',
          project_name=None, exact_timestamps=False, **kwargs):
    """Wrapper for copying files to and from s3 bucket.

    Args:
        ctx: Run context
        cmd: The aws s3 sub-command. Currently `cp` and `sync` are supported.
        simple_path: If specified, constructs local_path and s3_uri from relative path provided, keeping same directory
            structure on s3 and locally. Does not support '../' or './'
        direction: `up` or `down`.  Whether to upload or download from aws s3
        bucket: Default s3cmd://dstack-storage.
        local_path: Local relative path
        s3_path: Path on s3 bucket.
        project_name: Over ride the default project name derived from directory name or .env file
        exact_timestamps: Useful for when syncing static files like CSS
        **kwargs:

    Returns:

    Raises:
        AttributeError: When neither simple_path nor s3_path and local_path are specified.

    """
    if not project_name:
        project_name = 'temp'

    if simple_path is not None:
        if s3_path is None:
            s3_uri = f'{bucket}/{project_name}/{simple_path}'
        else:
            s3_uri = f'{bucket}/{s3_path}'

        if local_path is None:
            local_path = simple_path

    elif s3_path and local_path:
        s3_uri = f'{bucket}/{s3_path}'
        local_path = local_path

    else:
        raise AttributeError('Must specify either simple path or both s3_path and local_path')

    # params = ' --exact-timestamps' if kwargs.get('exact_timestamps', False) else ''
    params = ' --exact-timestamps' if exact_timestamps else ''
    template = f'{local_path} {s3_uri}' if direction == 'up' else f'{s3_uri} {local_path}'
    return do(ctx, cmd=f'aws s3 {cmd}{params} {template}', **kwargs)


@task
def mysql(ctx, cmd, project='toolset', service='mysql', tag='latest'):
    file_name = f'dump_{tag}.sql'
    backup_path = f'/srv/apps/{project}/backups'
    container = f'{project}_{service}_1'

    backup_cmd = ' '.join([
        'mysqldump', '-usuperset', '-psuperset', 'superset',
        '--complete-insert', '--add-drop-trigger',
        '--result-file=/opt/backup.sql'])

    backup_file = os.path.join(backup_path, file_name)
    restore_cmd = f'mysql -usuperset -psuperset superset < {backup_file}'

    if cmd == 'backup':
        docker(ctx, cmd=f'exec {container} bash -c "{backup_cmd}"')
        docker(ctx, cmd=f'cp {container}:/opt/backup.sql {backup_path}/{file_name}')
        s3cmd(ctx, local_path=backup_file, s3_path=f'{project}/backups/')

    elif cmd == 'restore':
        docker(ctx, cmd=f'exec -i {container} {restore_cmd}')


@task
def postgres(ctx, cmd, project=None, database=None, tag='latest'):
    """

    Args:
        ctx: The task context
        cmd: `backup` or `restore`
        tag: What to call the backup. By default it uses the current timestamp.
        project: Use this to override if the project path is different that the project name.
        database: Use this parameter if the database has a different name than the project.

    Returns:
        None

    """
    host = getattr(ctx, 'host', False)

    if project is None:
        # import pdb; pdb.set_trace()
        project = ctx['project_name']

    if database is None:
        database = project

    if host:
        project_path = f'/srv/apps/{project}'
    else:
        project_path = env.pwd

    compose(ctx, cmd='stop postgres', path=project_path)

    backup_dir = f'{project_path}/.local/backups'

    data_volume = f'{database}_dbdata'
    backup_name = f'db_backup.{tag}.tar.gz'
    fix = '&& chmod -R 700 /data'
    template = '--help'

    components = [
        'run',
        '--rm',
        f'-v {data_volume}:/data',
        f'-v {backup_dir}:/backup',
        'postgres:9.5',
    ]

    if cmd == 'backup':
        components.append(f'tar -zcpf /backup/{backup_name} /data')
        template = ' '.join(components)

        # docker docker run --rm -v plantsecure_dbdata:/data
        # -v /srv/apps/plant_secure/var/backups:/backup postgres:9.5
        # bash -c "tar xpf /backup/db_backup.test.tar.gz && chmod -R 700 /data"

    elif cmd == 'restore':
        components.append(f'bash -c "tar xpf /backup/{backup_name} {fix}"')
        template = ' '.join(components)

    docker(ctx, cmd=template)

    compose(ctx, cmd='start postgres', path=project_path)


@task
def mkdir(ctx, path):
    if sys.platform == 'win32':
        do(ctx, f'mkdir {path}')
    elif sys.platform == 'unix':
        do(ctx, f'mkdir -p {path}')


# Local task
# @task
def filer(content, key, bucket_name='dstack-storage', dry_run=False):
    # import pdb; pdb.set_trace()
    # host = env.hosts[0]
    # if local:
    #     ctx.local(f'scp {local_path} {host}:{remote_path}')
    # else:
    #     ctx.run(f'scp {local_path} {host}:{remote_path}')

    if not dry_run:
        s3 = boto3.resource('s3')
        file_object = s3.Object(bucket_name=bucket_name, key=key)
        file_object.put(Body=content.encode('utf-8'))
    else:
        content = content[:10] + '...'
        f'[local] aws s3 cp "{content}" s3://{bucket_name}/{key}'
