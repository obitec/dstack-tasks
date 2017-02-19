from invoke import task

from .base import do


@task
def make_docs(ctx):
    """Build html docs

    """
    do(ctx, 'sphinx-apidoc -f -o docs/modules dstack_factory')
    do(ctx, 'make html', path='docs')


@task
def clean(ctx, docs=False, venv=False, extra=''):
    patterns = ['build', '*.egg-info', 'dist']
    if docs:
        patterns.append('docs/_build')
    if venv:
        patterns.append('venv')
    if extra:
        patterns.append(extra)
    for pattern in patterns:
        do(ctx, f'rm -rf {pattern}')


@task
def build(ctx, docs=False):
    do(ctx, "python setup.py sdist bdist_wheel")
    if docs:
        do(ctx, "sphinx-build docs docs/_build")


@task
def contribute(ctx):
    do(ctx, 'python3.6 -m venv venv')
    do(ctx, 'source venv/bin/activate')
    build(ctx, docs=True)
