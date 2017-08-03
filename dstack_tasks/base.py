import logging
import os
import posixpath
from distutils.util import strtobool

import colorama
from dotenv import load_dotenv
from invoke import Config
from invoke import task
from invoke.env import Environment
from setuptools_scm import get_version

conf = Config()
env = Environment(config=conf, prefix='')
env.load()

# Global config
env.log_level = logging.INFO
env.pwd = os.getcwd()
env.src = os.path.join(env.pwd, 'src')
env.directory = os.path.basename(env.pwd)
env.remote = False
env.dry_run = False

# Attempt to get a version number
try:
    # env.version = get_version(root='.', relative_to=env.pwd)
    env.version = get_version()
except LookupError:
    try:
        with open(os.path.join(env.src, 'version.txt')) as f:
            env.version = f.readline().strip()
    except FileNotFoundError:
        env.version = os.getenv('VERSION', '0.0.0-dev')

env.tag = env.version


@task
def t1(ctx):
    # import pdb; pdb.set_trace()
    ctx.update({'foo': 'bar'})


@task
def t2(ctx):
    print(ctx.get('foo', 'not-configure'))
    print(env.version)
    print(env.src)


# noinspection PyUnusedLocal
@task
def e(ctx, collection=None, tag=None, live=False):
    """Set environment

    Optionally run before other task to configure environment

    Task to set the tag during runtime.

    Args:
        ctx: Context.
        collection: Used to specify a local collection of env settings.
            Useful when having different setups like staging/production/etc
        tag: The tag, preferably a SemVer version compatible string.
        live: Whether to run the command locally or on the server

    Returns:
        The tag supplied

    Examples:
        fab e:tag=v1.0.0 echo  # outputs the env with updated tag

    Configure local paths and settings

    Will also load .env files and <collection>.env files
    if python-dotenv is installed. <collection.env> files are stored in
    the project root under the .local folder and should not be checked into version control.

    Args:
        collection: The <collection>.env file that should be loaded before a task is executed.

    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    # Read collection.env overrides and then main local .env
    # because load_dotenv does not override env variables
    ctx.local_dotenv_path = os.path.join(env.pwd, '.env')
    if collection:
        load_dotenv(os.path.join(env.pwd, '.local', collection + '.env'))
    load_dotenv(ctx.local_dotenv_path)

    ctx.update({
        'tag': tag or env.tag,  # Allows working with a specific version to e.g. backup a database
        'live': live,
        'src': os.getenv('SOURCE_DIR', env.src),

        'project_name': os.getenv('PROJECT_NAME', env.directory),
        'organisation': os.getenv('ORGANISATION', ''),
        'git_repo': os.getenv('GIT_REPO', ''),
        'venv_name': os.getenv('VENV_NAME', ''),
        'venv_type': os.getenv('VENV_TYPE', 'conda'),
        'image_name': os.getenv('IMAGE_NAME', ''),

        'node_modules_prefix': os.getenv('NODE_PREFIX', '.local'),
    })

    if not ctx.image_name:
        ctx.image_name = ctx.organisation + '/' + (env.directory if not ctx.project_name else ctx.project_name)

    # Guess the virtual env
    ctx.venv_name = ctx.venv_name or ctx.project_name if ctx.venv_type == 'conda' else 'venv'

    # path to node modules
    ctx.node_modules = os.path.join(env.pwd, ctx.node_modules_prefix, '/node_modules/.bin/')

    # template for activating the python virtual environment
    activate = {
        'conda': {
            'posix': 'source activate {venv}',  # $ source activate <venv>
            'nt': 'activate {venv}'  # C:\> activate <venv>
        },
        'pip': {
            'posix': 'source {venv}/bin/activate',  # $ source <venv>/bin/activate
            'nt': r'{venv}\Scripts\activate.bat',  # C:\> <venv>\\Scripts\\activate.bat
            # PS C:\> <venv>\\Scripts\\Activate.ps1
        }
    }
    ctx.activate = activate[ctx.venv_type][os.name].format(venv=ctx.venv_name)

    # Setup specific to remote server
    # Configure paths
    path_config = {
        'apps': '/srv/apps',
        'volumes': {
            'postgres_data': '/var/lib/postgresql/data',
        }
    }

    project_dir = posixpath.join(path_config['apps'], ctx.project_name)

    remote = dict(
        project_dir=project_dir,
        server_dotenv_path=posixpath.join(project_dir, '.env'),
        postgres_data=path_config['volumes']['postgres_data'],
        virtual_host=os.getenv('VIRTUAL_HOST', ctx.project_name),
    )

    # Configure deployment
    ctx.remote = remote

    # Try to get the host_name
    env.hosts = [os.getenv('HOST_NAME', None), ]


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
def do(ctx, cmd, dry_run=None, local=False, host=None, **kwargs):
    """Base `run` task with support for dry run changing paths and setting environmental variables.

    Args:
        ctx:
        cmd: The command to execute, e.g. 'ls'
        dry_run: Override the the env.dry_run variable.
        local: Whether to run locally or not.
        host:
        **kwargs: path, host,

    Returns:

    """
    # TODO: Optionally load fabric Connection if host is defined

    # import pdb; pdb.set_trace()
    run_env = kwargs.pop('env', {})
    path = kwargs.pop('path', None)
    host = getattr(ctx, 'host', False)

    if dry_run is None:
        dry_run = env.dry_run

    if path:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
        # Only test if running locally, Python code always execute locally, not on host.
        if not host and not os.path.isdir(path):
            raise NotADirectoryError(f'{path}')

    if dry_run:
        cmd_str = []
        if run_env:
            # noinspection PyUnresolvedReferences
            env_vars = 'export ' + ' '.join(f'{k}={v}' for k, v in run_env.items())
            cmd_str.append(env_vars)
        if path:
            cmd_str.append(f'cd {path}')
        cmd_str.append(cmd)

        local_or_remote = colorama.Fore.YELLOW + '[local]' if not host or local else colorama.Fore.RED + '[remote]'
        print(local_or_remote, colorama.Fore.RESET + ' && '.join(cmd_str))

    else:
        if not path:
            if local:
                return ctx.local(cmd, env=run_env, **kwargs)
            else:
                # TODO: env isn't passed on to fabric connection.
                # Ways to work around this:
                # 1. use ctx.prefix
                # 2. Figure out cxn = Connection(..).run()
                # 3. File bug report for env
                return ctx.run(cmd, env=run_env, **kwargs)
        else:
            with ctx.cd(path):
                if local:
                    return ctx.local(cmd, env=run_env, **kwargs)
                else:
                    return ctx.run(cmd, env=run_env, **kwargs)


@task
def echo(ctx):
    """Task useful for debugging env variables and double checking context.

    Returns:
        Fabric env variables as set by config files, environmental variables, etc.

    """
    from pprint import pprint
    show_envs = [
        'pwd',
        'directory',
        'src',
        'log_level',
        'dry_run',
        'remote',
    ]

    custom_envs = {your_key: getattr(env, your_key, None) for your_key in show_envs}
    pprint('env')
    pprint(custom_envs)

    show_ctx = [
        'remote',
        'server_dotenv_path',
        'local_dotenv_path',
        'venv_name',
        'venv_type',
        'virtual_host',
        'image_name',
        'tag',
        'organisation',
        'git_repo',
    ]

    custom_ctx = {your_key: getattr(ctx, your_key, None) for your_key in show_ctx}
    pprint('ctx')
    pprint(custom_ctx)

    return custom_envs
