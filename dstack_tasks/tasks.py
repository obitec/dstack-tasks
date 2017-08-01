import os
from datetime import datetime

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
        set_key(dotenv_path='./stack/{base_service}/.env',
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
        s3cmd(ctx, simple_path=f'dist/{project_name}-{version}-py3-none-any.whl', direction='up',
              project_name=project_name)

    # aws s3 sync ./.local/static/ s3://dstack-storage/toolset/static/v1/
    if static:
        ignore = ['test', 'docs', '*.md', '*.txt', '*.sass', '*.less', '*.html', 'LICENSE', '*.coffee']
        ignore_params = ' -i '.join(ignore)

        python(ctx, cmd=f'./src/manage.py collectstatic -v0 -i {ignore_params}', conda_env=True)
        # --exact-timestamps
        # s3cmd(ctx, cmd='sync', local_path='./.local/static/', s3_path=f'static/v0.18.10/', exact_timestamps=True)
        # TODO: Once webpack has been integrated, use version tag instead of `latest`
        s3cmd(ctx, cmd='sync', local_path='./.local/static/', s3_path=f'{project_name}/static/latest/',
              exact_timestamps=True)


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
