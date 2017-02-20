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
def s3(ctx, cmd='cp', simple_path=None, direction='up', local_path=None, s3_path=None, bucket='s3://dstack-storage',
       project_name=None, **kwargs):
    """Wrapper for copying files to and from s3 bucket.

    Args:
        ctx: Run context
        cmd: The aws s3 sub-command. Currently `cp` and `sync` are supported.
        simple_path: If specified, constructs local_path and s3_uri from relative path provided, keeping same directory
            structure on s3 and locally. Does not support '../' or './'
        direction: `up` or `down`.  Whether to upload or download from aws s3
        bucket: Default s3://dstack-storage.
        local_path: Local relative path
        s3_path: Path on s3 bucket.
        project_name:
        **kwargs:

    Returns:

    Raises:
        AttributeError: When neither simple_path nor s3_path and local_path are specified.

    """
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

    up_template = f'{cmd} {local_path} {s3_uri}'
    down_template = f'{cmd} {s3_uri} {local_path}'
    template = up_template if direction == 'up' else down_template

    return do(ctx, cmd=f'aws s3 {template}', **kwargs)
