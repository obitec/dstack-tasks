import os

from invoke import task

from .base import do, env


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
def python(ctx, cmd='--help', venv=True, **kwargs):
    """System python wrapper with venv activation.

    Args:
        ctx:
        cmd:
        venv:
        **kwargs:

    Returns:

    """
    venv = env.activate if venv else ''
    return do(ctx, f'{venv}python {cmd}', **kwargs)


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
def s3cp(ctx, file_path, direction='down', bucket='s3://dstack-storage', project_name=None, **kwargs):
    """

    Args:
        ctx: context
        file_path: The file path to be copied relative to current working directory. Does not support '../' or './'
        direction: `up` or `down`. Whether to upload or download from aws s3
        bucket:
        project_name:
        **kwargs:

    Returns:

    """
    project_name = project_name or os.path.basename(os.getcwd())

    remote_path = f'{bucket}/{project_name}/{file_path}'
    cmd = f'cp {file_path} {remote_path}' if direction == 'up' else f'cp {remote_path} {file_path}'

    return do(ctx, cmd=f'aws s3 {cmd}', **kwargs)
