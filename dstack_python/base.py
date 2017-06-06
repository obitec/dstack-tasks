import os
import sys

from fabric.colors import red
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


# noinspection PyUnusedLocal
@task
def dry(ctx):
    """Print task commands instead of executing them

    Args:
        ctx: Run context.

    Returns:

    """
    env.dry_run = True


# noinspection PyUnusedLocal
# @task
def do(ctx, cmd, dry_run=None, **kwargs):
    """Base `run` task with support for dry run changing paths and setting environmental variables.

    Args:
        ctx:
        cmd: The command to execute, e.g. 'ls'
        dry_run: Override the the env.dry_run variable.
        **kwargs: path, host, 

    Returns:

    """
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
            # noinspection PyUnresolvedReferences
            env_vars = 'export ' + ' '.join(f'{k}={v}' for k, v in run_env.items())
            cmd_str.append(env_vars)
        if path:
            cmd_str.append(f'cd {path}')
        cmd_str.append(cmd)

        print(red('local:'), ' && '.join(cmd_str))

    else:
        if not path:
            return run(cmd, env=run_env, **kwargs)
        else:
            with cd(path):
                return run(cmd, env=run_env, **kwargs)
