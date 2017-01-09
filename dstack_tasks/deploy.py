import io
import os
from distutils.util import strtobool

from fabric.api import env
from fabric.colors import yellow, red
from fabric.context_managers import prefix
from fabric.decorators import task
from fabric.operations import prompt, local
from .utils import dirify, vc
from .wrappers import compose, docker, execute, postgres, manage, git, filer
import os.path


@task
def make_wheels(package: str = None) -> None:
    """Build wheels for python packages

    Creates wheel package for each dependency specified in build-reqs.txt (if it exists) else
    relies on the main packages's setup.py file to find and build dependencies.

    Args:
        package (str): The primary package. Any input accepted by pip is accepted here. E.g.:
            `dstack-tasks` or `dstack-tasks>1.0.0`.

    See also:
        :py:func:`make_default_webapp` Uses these wheels to create a docker runtime with only the minimal
        libraries required to run the primary package.

    Returns:
        None

    Raises:
        AttributeError: Raised when neither a package nor a build-reqs.txt is specified.

    Warnings:
        This function requires a working `wheels-factory <https://github.com/obitec/wheel-factory/>`_ to be running on the specified server.

    Note:
        This task can be run on a different server that the one being deployed to by supplying the ``hosts``
        command line argument.


    """
    build_dir = dirify(env.build_dir, force_posix=True)

    if os.path.exists('build-reqs.txt'):
        filer(cmd='put', local_path='build-reqs.txt', remote_path=build_dir('build-requirements.txt'))

    elif package:
        filer(cmd='put', local_path=io.StringIO(package), remote_path=build_dir('build-requirements.txt'))

    else:
        raise AttributeError('Either a package must be specified or build-reqs.txt must exist.')

    execute('rm -rf *.whl', path=build_dir('wheelhouse'), live=True)

    compose(cmd='-f service.yml -p %s run --rm wheel-factory' % env.project_name, path=build_dir(''), live=True)


@task
def make_default_webapp(tag: str = 'latest', package: str = None) -> None:
    """Builds a docker image that contains the necessary libraries and dependencies to run the
    specified package from.

    Note:
        This task requires that the package has a setup.py file that lists all its dependencies
         in ``install_requires``. If this is not the case, an optional ``requirements.txt`` can be supplied.

    Args:
        package: The name and optional version of package to build a docker image for.
            Can be any format that is accepted by pip, including GitHub links.
        tag: The SemVer Tag

    Returns:
        None

    """

    if os.path.exists('requirements.txt'):
        filer(cmd='put', local_path='./requirements.txt', remote_path='/srv/build/requirements.txt')

    # TODO: make path configurable and locally executable
    execute('docker build -t {image_name}:{image_tag} .'.format(
        image_name=env.image_name, image_tag=tag), path='/srv/build', live=True)


@task
def push_image(tag: str = 'latest', live: bool = False) -> None:
    """Wrapper to simplify pushing an image to DockerHub

    """
    docker('push %s:%s' % (env.image_name, tag), path='', live=live)


@task
def ci(tag: str) -> None:
    """**Deprecated**. See :py:func:`deliver`.

    Todo:
        Migrate version control logic to :py:func:`release_tag`

    """

    answer = prompt('Did you remember to first commit all changes??', default='no', )
    if answer == 'yes':
        try:
            local('git tag %s' % tag)
        except SystemExit:
            print(yellow('Git tag already exists'))

        postgres('backup', live=False, tag=tag)

        try:
            docker('tag {image_name}:latest {image_name}:{tag}'.format(
                image_name=env.image_name, tag=tag))
            docker('tag {image_name}:production {image_name}:{tag}-production'.format(
                image_name=env.image_name, tag=tag))
        except SystemExit:
            print(red('Docker image :latest not found'))

    else:
        print("# Commit changes using:\n$ git commit -a -m 'message...'")

    postgres(cmd='backup', tag=tag + '-staging', live=True)

    answer = prompt('Did you update or add dependencies?', default='no', )
    if answer == 'yes':
        make_wheels()
        make_default_webapp()
        # push_image(tag=tag, live=True)

    answer = prompt('Do you want to test db migration now?', default='yes', )
    if answer == 'yes':
        postgres(cmd='restore', tag=tag + '-staging', live=False, sync_prompt=True)
        manage('migrate')

    answer = prompt('Do you want to restore local db?', default='no', )
    if answer == 'yes':
        postgres(cmd='restore', tag=tag + '-development', live=False)

    answer = prompt('Was it successful? Do you want to deploy', default='no', )
    if answer == 'yes':
        tag = vc()
        execute("sed -i .bak 's/RELEASE_TAG.*/RELEASE_TAG=%s/g' '.env'" % tag, live=False)
        # deploy()
        build(live=True)
        # postgres(cmd='restore', tag=tag + '-staging', live=True)
        manage('migrate', live=True)
        compose(cmd='up -d', live=True)

        answer = prompt('Did the app successfully update?', default='yes', )
        if answer == 'yes':
            # snapshot(tag=tag, live=True)
            push_image(tag=tag, live=True)

        print('Successfully deployed app %s!' % tag)


@task
def build(live: bool = False) -> None:
    """High level function to build webapp

    Warnings:
        **Deprecated**: See :py:func:`deploy_runtime`.
    """

    execute('git pull', live=live)
    with prefix('export UID'):
        compose('up static_builder', live=live)
        compose('up static_collector', live=live)
        compose('up volume_fixer', live=live)

    execute("rsync -avz --exclude-from 'etc/exclude-list.txt' ./src/ etc/webapp/build/", live=live)

    with prefix('export UID'):
        compose('build webapp', live=live)


@task
def build_code(live: bool = False, migrate: bool = False) -> None:
    """High level function to build runtime

    Warnings:
        **Deprecated**: See :py:func:`build_runtime`.
    """
    execute('git pull', live=live)
    execute("rsync -avz --exclude-from 'etc/exclude-list.txt' ./src/ etc/webapp/build/", live=live)

    with prefix('export UID'):
        compose('build webapp', live=live)

    if migrate:
        manage('migrate', live=live)

    compose('up -d webapp', live=live)


@task
def release_runtime(tag: str = 'latest') -> None:
    """Rebuilds the docker container for the python runtime and push a tag image to to DockerHub.

    Note:
        Does not affect current running webapp. This task is safe, it does not affect the production runtime!

    Args:
        tag: Name of release, preferably a SemVer version number

    Returns:
        None
    """

    make_wheels()
    make_default_webapp(tag=tag)
    # TODO: should be able to specify private repo

    docker('tag {image_name}:{tag} {image_name}:latest'.format(
        image_name=env.image_name, path='', tag=tag), live=True)

    push_image(tag=tag, live=True)

    # TODO: Figure out a way to keep latest up to date
    push_image(tag='latest', live=True)


@task
def release_code(tag: str = 'latest') -> None:
    """Commits, tags and pushes tag to GitHub

    Note:
        This task is safe, it does not affect the production runtime!

    Args:
        tag: Name of release, preferably a SemVer version number

    """
    # TODO: Replace with actually checking for clean tree
    answer = prompt('Did you remember to first commit all changes??', default='no', )
    if answer == 'yes':
        if tag == 'latest':
            git('push origin master')
        else:
            try:
                git('tag %s' % tag)
            except SystemExit:
                print(yellow('Git tag already exists'))
            git('push origin {tag}'.format(tag=tag))


@task
def release_data(tag: str = 'latest') -> None:
    """Backup and upload tagged version of database

    Note:
        This task is safe, it does not affect the production runtime!

    Args:
        tag: Name of release, preferably a SemVer version number

    Returns:
        None

    Todo:
        * Implement S3(?) database/fixture/view storage
        * Implement cloud storage for media + static files
    """
    # TODO: Implement S3(?) database/fixture/view storage
    # TODO: Implement cloud storage for media + static files
    print('Not implemented! ' + tag)

    # raise NotImplementedError


@task
def release_tag(tag: str = 'latest') -> None:
    """Convenience task that release a named version of the runtime, code and data

    Args:
        tag: Name of release, preferably a SemVer version number

    Returns:
        None

    """
    answer = prompt('Did you make changes the database?', default='no', )
    if answer == 'yes':
        release_data(tag=tag)

    answer = prompt('Did you update the code?', default='no', )
    if answer == 'yes':
        release_code(tag=tag)

    answer = prompt('Did you update python dependencies?', default='no', )
    if answer == 'yes':
        release_runtime(tag=tag)
    else:
        docker('tag {image_name}:latest {image_name}:{tag}'.format(
            image_name=env.image_name, tag=tag), live=True)
        # push_image(tag=tag, live=True)
        docker('push %s:%s' % (env.image_name, tag), path='', live=True)


@task
def build_runtime(tag: str = 'latest', instance: str = 'production', image_name: str = None, live: bool = True) -> None:
    """Builds the production runtime

    This task is safe, it does not affect the running instance!
    The next restart, however, might change the runtime.

    """
    if not isinstance(live, bool):
        live = bool(strtobool(live))

    image_name = image_name or env.image_name

    # Pull latest docker version
    answer = prompt('Did you update the base image?', default='no', )
    if answer == 'yes':
        docker('pull {image_name}:{image_tag}'.format(image_name=image_name, image_tag=tag), live=True)
        docker('pull {image_name}:latest'.format(image_name=image_name), live=True)
        # docker('tag {image_name}:{tag} {image_name}:latest'.format(
        #     image_name=image_name, tag=tag), live=True)

    if live:
        git('fetch --all', live=True)
        answer = prompt('Checking out a tag?', default='yes', )
        if answer == 'yes':
            git('checkout --force {tag}'.format(tag=tag), live=True)
        else:
            git('checkout --force origin/master', live=True)

    # execute("rsync -avz --exclude-from '.dockerignore' ./src/ .local/build/", live=True)

    env.image_tag = '{tag}-{instance}'.format(tag=tag, instance=instance)
    # env.image_tag = tag + '-production'
    # with prefix('export UID'):
    docker('tag {image_name}:{tag} default_webapp'.format(
        image_name=image_name, tag=tag), path='', live=live)

    compose('build webapp', live=live)


@task
def deploy_runtime(tag: str = 'latest', instance: str = 'production', first: bool = False) -> None:
    """
    Deploys production runtime.

    This function is not safe and requires a database
    backup before running!

    Args:
        tag: the general version of the image name, e.g organization/project:tag
            this is the base image, it contains the necessary runtime,
            but not the code and runs as root user.
        instance: this is the specific instance of the runtime that is being used and
            contains everything necessary to run an immutable server.
            E.g. organization/project:tag-instance
            (where instance can be production, alpha, beta, or a1, a2 etc). This container also runs
            as the restricted 'webapp' user. This is useful for rapid development where the runtime
            does not necessarily change, but the code is updated. Default is production.
        first: First initialise (git clone, etc) the webapp before updating and deploying it.

    """

    env.image_tag = '{tag}-{instance}'.format(tag=tag, instance=instance)

    if first:
        compose('up -d webapp', live=True)
        manage('migrate', live=True)
        manage('loaddata config/fixtures/initial_data.json', live=True)

    else:
        answer = prompt('Did you want to migrate?', default='no', )

        if answer == 'yes':
            answer = prompt('Do you want to create a backup?', default='yes', )
            if answer == 'yes':
                postgres(cmd='backup', tag=tag + '-rollback', live=True)
            manage('migrate', live=True)
            answer = prompt('Was the migration successful?', default='yes', )
            if answer == 'no':
                postgres(cmd='restore', tag=tag + '-rollback', live=True)
                raise Exception('Deployment failed')

    compose('up -d webapp', live=True)

    with prefix('export UID'):
        env.image_tag = tag
        # compose('up static_builder', live=live)
        compose('up static_collector', live=True)
        compose('up volume_fixer', live=True)


@task
def deliver(tag: str = 'latest', instance: str = 'production', image_name: str = None, first: bool = False) -> None:
    """From build to deploy!

    Main task for delivering a new task to the server.

    Args:
        tag: Preferably a SemVer version number, e.g. 1.2.10.
            Used to identify the git tag, docker tag and database backup tag.
        instance: Distinguishes the final immutable image from the base image. e.g. 1.2.10-production.
        image_name: Used to override the image_name retrieved from the env dict.
        first: Initialize the project if True, otherwise update it.

    """
    release_tag(tag=tag)

    if first:
        # TODO: Put org in the env config
        init_deploy(org=None)
        copy_envs()

    build_runtime(image_name=image_name, tag=tag, instance=instance)
    deploy_runtime(tag=tag, instance=instance, first=first)


@task
def create_github_repo():
    """ Needed for when dstack tasks is standalone invoke tool to manage full workflow

    Warning:
        Work in progress.

    Returns:
        None

    """
    # TODO: Make this work!
    import requests
    r = requests.get('https://api.github.com', auth=('user', 'pass'))
    print(r.status_code)
    print(r.headers['content-type'])

@task
def copy_envs(env_path: str = '.local'):
    """Copy over config files required by docker-compose containers

    Args:
        env_path:

    Returns:
        None

    """
    filer('put', local_path='{path}/*.env'.format(path=env_path), remote_path='/srv/apps/{project}/{path}/'.format(
        project=env.project_name, path=env_path))


@task
def init_deploy(org: str, ssh: bool = False):
    """Task for initialising webapps deployed for the first time.

    Args:
        org: The organisation name, used in constructing the docker tag
        ssh: Use ssh style GitHub cloning if True, https style if False

    Returns:
        None

    Todo:
        Make distinction between project name and GitHub name. Also allow other git repos/hosts

    """

    if org:
        env.organisation = org

    if ssh:
        git(cmd='clone git@github.com:{}/{}.git {}'.format(env.organisation, env.git_repo, env.project_name),
            path='/srv/apps', live=True)
    else:
        git(cmd='clone https://github.com/{}/{} {}'.format(env.organisation, env.git_repo, env.project_name),
            path='/srv/apps', live=True)

    execute('mkdir -p .local', live=True)
    execute('mkdir -p src/static', live=True)

    # TODO: Make this work. Maybe check out dockergen templating or add to server install
    execute('cp /srv/nginx/templates/nginx-vhost.conf /srv/nginx/vhost.d/{}'.format(env.virtual_host),
            path='', live=True)
    execute("sed -i.bak 's/{{project_name}}/%s/g' '/srv/nginx/vhost.d/%s'" % (
        env.project_name.replace('.', '\.'), env.virtual_host), path='', live=True)


# @task
# def copy_envs():
#     put('.local/*', '/srv/apps/{}/.local/'.format(env.project_name))


# INSTALL Virtualenv kernal python:
# OUTDATED but with correct path to copy:
# http://help.pythonanywhere.com/pages/IPythonNotebookVirtualenvs

# Correct usage:
# https://github.com/ipython/ipykernel/issues/52#issuecomment-212001601

