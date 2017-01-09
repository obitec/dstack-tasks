import sys

from invoke import Config
from invoke import run, task
from invoke.env import Environment
from invoke.util import cd

conf = Config()
env = Environment(config=conf, prefix='')
env.load()


env.directory = './'
env.activate = 'source venv/bin/activate && '


@task
def pip(ctx, cmd='list', venv=True):
    venv = env.activate if venv else ''
    run('{venv}pip {cmd}'.format(**locals()))


@task
def mkdir(ctx, path):
    if sys.platform == 'win32':
        run('mkdir %s' % path)
    elif sys.platform == 'unix':
        run('mkdir -p %s' % path)


@task
def test_setup(ctx):
    pip('install -r tests/requirements.txt')
    pip('install -U .')


@task
def create_test_app(ctx):
    """Create a test app structure

    :return:
    """
    mkdir(path='tests')
    with cd('tests'):
        run('django-admin startproject config .')


@task
def docs(ctx):
    """Build html docs

    """
    run('sphinx-apidoc -f -o docs/modules dstack_tasks')

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
    run("python setup.py sdist bdist_wheel")
    if docs:
        # run('sphinx-apidoc -f -o docs/modules dstack_tasks')
        run("sphinx-build docs docs/_build")


@task
def runserver(ctx):
    run("python tests/manage.py runserver", )


@task
def contribute(ctx):
    run('pyvenv-3.5 venv')
    run('. venv/bin/activate')
    run('pip install -r tests/requirements.txt')
    build(docs=True)
