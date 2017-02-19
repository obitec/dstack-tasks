import os
import sys

from setuptools_scm import get_version
import sh
from compose.cli.command import get_project
from dotenv import set_key
from invoke import Config
from invoke import run, task
from invoke.env import Environment
from invoke.util import cd

conf = Config()
env = Environment(config=conf, prefix='')
env.load()

env.directory = './'
env.activate = 'source venv/bin/activate && '

# env.activate = 'source activate project_name && '

env.dry_run = False


@task
def dry(ctx):
    env.dry_run = True


@task
def do(ctx, cmd, dry_run=None, **kwargs):
    run_env = kwargs.pop('env', {})
    path = kwargs.pop('path', None)

    if path:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        if not os.path.isdir(path):
            raise NotADirectoryError(f'{path}')

    if dry_run is None:
        dry_run = env.dry_run

    if dry_run:
        cmd_str = []
        if run_env:
            env_vars = 'export ' + ' '.join(f'{k}={v}' for k, v in run_env.items())
            cmd_str.append(env_vars)
        if path:
            cmd_str.append(f'cd {path}')
        cmd_str.append(cmd)

        print(' && '.join(cmd_str))

    else:
        if not path:
            return run(cmd, env=run_env, **kwargs)
        else:
            with cd(path):
                return run(cmd, env=run_env, **kwargs)


@task
def test(ctx, cmd='ls', path='.', dry_run=False):
    # env.dry_run = dry_run
    # do(ctx, cmd=cmd, path=path)
    # print(ctx)
    do(ctx, 'echo $FOO', env={'FOO': 'bar'})


@task
def docker(ctx, cmd='--help', **kwargs):
    return do(ctx, f'docker {cmd}', **kwargs)


@task
def compose(ctx, cmd='--help', **kwargs):
    return do(ctx, f'docker-compose {cmd}', **kwargs)


@task
def git(ctx, cmd='--help', **kwargs):
    return do(ctx, f'git {cmd}', **kwargs)


@task
def install(ctx, push=True, py_version=3.5, **kwargs):
    compose(ctx, 'build factory', path='.', **kwargs)
    compose(ctx, 'build runtime', path='.', **kwargs)
    if push:
        docker(ctx, f'push obitec/dstack-factory:{py_version}')
        docker(ctx, f'push obitec/dstack-runtime:{py_version}')


@task
def package(ctx, package_name, version, c_ext=False):
    install(ctx, push=True)

    recipe = f'{package_name}-{version}'

    with open(f'recipes/{recipe}.txt', 'w+') as f:
        f.write(f'{package_name}=={version}')

    compose(ctx, 'run --rm factory', env={'CEXT': c_ext, 'RECIPE': f'{recipe}'})


@task
def demo(ctx):
    package(ctx, 'django', '1.10.5')


@task
def python(ctx, cmd='--help', venv=True, **kwargs):
    venv = env.activate if venv else ''
    return do(ctx, f'{venv}python {cmd}', **kwargs)


@task
def pip(ctx, cmd='list', venv=True, **kwargs):
    return python(ctx, cmd=f'-m pip {cmd}', venv=venv, **kwargs)


@task
def s3cp(ctx, file_path, direction='down', bucket='s3://dstack-storage', project_name='default', **kwargs):
    """

    :param ctx:
    :param file_path:
    :param direction:
    :param bucket:
    :param project_name:
    :param kwargs:
    :return:
    """
    remote_path = f'{bucket}/{project_name}/{file_path}'
    cmd = f'cp {file_path} {remote_path}' if direction == 'up' else f'cp {remote_path} {file_path}'

    return do(ctx, cmd=f'aws s3 {cmd}', **kwargs)


@task
def deploy(ctx, project_name=None, version='0.0.0'):
    """

    :param ctx:
    :param project_name: As written the *.whl file.
    :param version: As stored in the *.whl file, e.g. 1.0.0
    :return:
    """
    project_name = project_name or os.path.basename(os.getcwd())

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
def release(ctx, project_name=None, version=None):
    project_name = project_name or os.path.basename(os.getcwd()).replace('-', '_')
    scm_version = get_version()

    print(f'Git version: {scm_version}')
    version = version or '.'.join(scm_version.split('.')[:3])

    if env.dry_run:
        print(sh.git.tag.bake(version))
    else:
        sh.git.tag(version)

    do(ctx, cmd='rm -rf dist/ build/ *.egg-info/')
    python(ctx, cmd='setup.py bdist_wheel', venv=True)

    s3cp(ctx, file_path=f'dist/{project_name}-{version}-py3-none-any.whl', direction='up', project_name=project_name)




@task
def mkdir(ctx, path):
    if sys.platform == 'win32':
        run('mkdir %s' % path)
    elif sys.platform == 'unix':
        run('mkdir -p %s' % path)


@task
def docs(ctx):
    """Build html docs

    """
    run('sphinx-apidoc -f -o docs/modules dstack_factory')

    with cd('docs'):
        run('make html')


@task
def clean(ctx, docs=False, bytecode=False, venv=False, extra=''):
    patterns = ['build', '*.egg-info', 'dist']
    if docs:
        patterns.append('docs/_build')
    if bytecode:
        patterns.append('**/*.pyc')
    if venv:
        patterns.append('venv')
    if extra:
        patterns.append(extra)
    for pattern in patterns:
        run("rm -rf %s" % pattern)


@task
def build(ctx, docs=False):
    do(ctx, "python setup.py sdist bdist_wheel")
    if docs:
        do(ctx, "sphinx-build docs docs/_build")


@task
def contribute(ctx):
    run('python3.6 -m venv venv')
    run('source venv/bin/activate')
    build(docs=True)


@task
def running_containers(ctx):
    """

    :return: List of running container names
    """
    result = docker(ctx, cmd='ps -a --format "table {{.Names}}"', hide=True)
    containers = result.stdout.split('\n')[1:-1]
    print(containers)

    return containers
