import os

import sh
from compose.cli.command import get_project
from dotenv import set_key
from invoke import task
from setuptools_scm import get_version

from .base import do, env
from .wrap import docker, git, python, s3cp


@task
def test(ctx):
    do(ctx, 'ls')


@task
def deploy(ctx, project_name=None, version='0.0.0'):
    """Download wheel from s3, set .env variables, build project and up it.

    Args:
        ctx:
        project_name: The name of the python package. If None, uses directory name with '_' replacing '-'.
        version: The python package version to deploy.

    Returns: Project status

    """
    project_name = project_name or os.path.basename(os.getcwd()).replace('-', '_')

    # aws s3 cp s3://dstack-storage/plant_secure/deploy/plant_secure-0.16.18-py3-none-any.whl ./
    s3cp(ctx, file_path=f'dist/{project_name}-{version}-py3-none-any.whl', project_name=project_name)

    # dotenv -f .env -q auto set VERSION version
    set_key(dotenv_path='.env', key_to_set='VERSION', value_to_set=version, quote_mode='auto')
    # dotenv -f .local/webapp.env -q auto set VERSION version
    set_key(dotenv_path='.local/webapp.env', key_to_set='VERSION', value_to_set=version, quote_mode='auto')

    project = get_project(project_dir='./')
    # docker-compose build webapp
    project.build(service_names=['webapp', ])
    # docker-compose up -d django
    project.up(service_names=['webapp', ], detached=True)


@task
def release(ctx, project_name=None, version=None, upload=True, push=False):
    """Tag, build and optionally push and upload new project release

    """
    project_name = project_name or os.path.basename(os.getcwd()).replace('-', '_')
    scm_version = get_version()

    print(f'Git version: {scm_version}')
    if len(scm_version.split('.')) > 3:
        print('First commit all changes, then run this task again')
        return False

    version = version or '.'.join(scm_version.split('.')[:3])

    if env.dry_run:
        print(sh.git.tag.bake(f'v{version}'))
    else:
        try:
            sh.git.tag(f'v{version}')
        except sh.ErrorReturnCode:
            print('Tag already exists!')
            return False

    # Clean and build
    do(ctx, cmd='rm -rf dist/ build/ *.egg-info/')
    python(ctx, cmd='setup.py bdist_wheel', venv=True)

    if push:
        git(f'push origin v{version}')

    if upload:
        s3cp(ctx, file_path=f'dist/{project_name}-{version}-py3-none-any.whl',
             direction='up', project_name=project_name)


@task
def docker_ps(ctx):
    """

    :return: List of running container names
    """
    result = docker(ctx, cmd='ps -a --format "table {{.Names}}"', hide=True)
    containers = result.stdout.split('\n')[1:-1]
    print(containers)

    return containers
