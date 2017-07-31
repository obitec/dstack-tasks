import io
import os
from distutils.util import strtobool
from typing import Union

from fabric.api import env
from fabric.colors import yellow, red
from fabric.context_managers import prefix, settings
from fabric.decorators import task
from fabric.operations import prompt, local, run
from .utils import dirify, vc
from .wrappers import compose, docker, execute, postgres, manage, git, filer, dotenv, s3, s3cp
import os.path


@task
def make_wheels(use_package: Union[str, bool] = None, use_recipe: Union[str, bool] = None,
                clear_wheels: bool = True, interactive: bool = True,
                py_version: str = '3.5', c_ext: bool = True) -> bool:
    """Build wheels for python packages

    Creates wheel package for each dependency specified in build-reqs.txt (if it exists) else
    relies on the main packages's setup.py file to find and build dependencies.

    Args:
        use_package: Default = None. If specified, use this single package as source for dstack-factory to find
            dependencies to build. Can be a local wheel file uploaded to dstack-factory archive or any package
            specification accepted by pip. If use_package ends in `.whl` `make_wheel` assumes that the package
            has already been uploaded to dstack-factory's archive.
            Examples: `{package}-{version}-py3-none-any.whl`, `dstack-tasks` or `dstack-tasks>1.0.0`.
        use_recipe: Default = None. Can be bool or str. If True, then use default recipe "build-reqs.txt". If no package
            is specified in `use_package`, then this pip requirements style file is uploaded and used as only source for
            dependencies. If a recipe is specified as well as a package, dependencies specified in the recipe will be
            build first and then the dependencies from the package.
            This allows fine grained control over which version or sources are used for packages. E.g. if
            "install_requires" specifies `celery`, but you don't want the version on PyPI, then you can specify a
            GitHub fork or any other source to install from in your recipe file.
        clear_wheels: Default = True. Clears the wheel packages before building. The theory is that if only the required
            wheel files are in the docker build context then the builds will be faster and the resulting image be
            smaller. This option is used when bothe use_packege and use_recipe has been given. This task then
            calls itself twice, once for building the recipe dependencies and then, without clearing the wheel files
            from previous build, build the dependencies as specified by the package.
        interactive: Default = True. Whether this task should prompt questions and reminders like reminding you
            to first upload your wheel package.
        py_version: Default = 3.5. Python 3.6 is also supported.
        c_ext: Default = True. Whether to build cython and numpy before rest of dependencies.

    See also:
        :py:func:`make_default_webapp` Uses these wheels to create a docker runtime with only the minimal
        libraries required to run the primary package.

    Returns:
        None

    Raises:
        AttributeError: Raised when neither a package nor a build-reqs.txt is specified.
        FileExistsError: Raised when wheel file is specified for package, but not uploaded to archive yet.
        FileNotFoundError: Raised when recipe file could not be found.

    Warnings:
        This function requires a working `dstack-factory <https://github.com/obitec/dstack-factory/>`_ to
        be running on the specified server.

    Note:
        This task can be run on a different server that the one being deployed to by supplying the ``hosts``
        command line argument, e.g.:
        fab e dry make_wheels:hosts=factory.obitec.co

        If you've got custom python dependencies, e.g. django-factbook, that has not yet been published to pip,
         just make sure to run make_wheels with `use_recipe=True` to first build build-req.txt dependencies
         containing the source url for custom pacakges.
         This will archive a wheel package for that dependency on dstack-factories archive and will be retrieved
         for the subsequent `package_build`.

    """
    env.live = True

    # Set the defaults
    build_dir = dirify(env.build_dir, force_posix=True)
    recipe_filename = 'requirements'

    # If neither parameters are given, use defaults for both (same as specifying True for both)
    if use_package is None and use_recipe is None:
        use_package = True
        use_recipe = True

    if use_package in [True, 'True', 'true', '1']:
        use_package = '{package}-{tag}-py3-none-any.whl'.format(package=env.project_name, tag=env.tag)
    if use_recipe in [True, 'True', 'true', '1']:
        use_recipe = 'build-reqs.txt'

    # This is the default way of building runtime images:
    # The .whl file created from "setup.py build bdist_wheel" will be used to get list of dependencies
    # dstack-factory will use the "install_requires" to determine what dependencies to create wheel files for.
    # This method works best if your dependencies are all released on pip
    if use_package and use_recipe:
        # Naive check to see if a matching .whl file has recently been built
        # TODO: test if it has actually been uploaded to archive and optionally download from s3 or upload if not
        wheel_file = '{package}-{tag}-py3-none-any.whl'.format(package=env.project_name, tag=env.tag)
        if not os.path.exists('dist/' + wheel_file):
            # raise AttributeError(
            #     'Trying to build wheels from project wheel, but build does not exist')
            print(red('ERROR: First build your file. {} does not exist.'.format(wheel_file)))
            return exit(1)

        make_wheels(use_recipe=use_recipe, interactive=False)
        make_wheels(use_package=use_package, clear_wheels=False, interactive=False)

        return True

    # Useful for something like superset that can be installed from pip or from arbitrary wheel file uploaded archive.
    # There is currently now difference between specify a .whl file or a pip package specification except that it
    # asks you if you've uploaded the file to the archive. This is because when dstack-factory builds wheels it checks
    # for existing wheels in archive before downloading from pip or other source.
    elif use_package and not use_recipe:
        # TODO: Also add support for s3 hosted .whl files, e.g. s3://dstack-storage/django-1.10.3-py3-none-any.whl
        # print(use_package[-4:])
        if use_package[-4:] == '.whl':
            # e.g. make_wheels(use_package='django-1.10.3-py3-none-any.whl')
            if interactive:
                answer = prompt('Did you remember to upload wheel package to dstack-factory archive?', default='yes')
            else:
                answer = 'no'

            package, tag = use_package.split('-', maxsplit=2)[:2]
            use_recipe = io.StringIO('{package}=={tag}'.format(package=package, tag=tag))

            if answer == 'no':
                wheel = '{package}-{tag}-py3-none-any.whl'.format(package=package, tag=tag)

                with settings(warn_only=True):
                    s3cp(simple_path='dist/{wheel}'.format(wheel=wheel),
                         local_path=build_dir('archive/'),
                         direction='down',
                         live=True)

            # else:
            #     raise FileExistsError('First upload the file before you continue!')
            #     print(red('ERROR: First upload the file before you continue'))
            #     return exit(1)
        else:
            # e.g. make_wheels(use_package='django==1.10')
            use_recipe = io.StringIO(use_package)

    # Use only a pip requirements file to build wheels. This is the old way of doing things and requires exact version
    # pinning for both creating the wheels as well as making the default_webapp.
    elif not use_package and use_recipe:
        if os.path.exists(use_recipe):
            recipe_filename = '{package}-{tag}'.format(package=env.project_name, tag=env.tag)
        else:
            # raise FileNotFoundError('Recipe file not found!')
            print(red('ERROR: Recipe file does not exist'))
            return exit(1)

    else:
        print(red('Invalid setup. Must specify either use_package, or use_recipe'))
        return exit(1)

    if clear_wheels:
        execute('rm -rf *.whl', path=build_dir('wheelhouse'))

    filer(cmd='put', local_path=use_recipe, remote_path=build_dir('recipes/{}.txt'.format(recipe_filename)))

    execute(
        cmd='export RECIPE={} PY_VERSION={} CEXT={} && docker-compose run --rm factory'.format(
            recipe_filename, py_version, c_ext),
        path=build_dir(''))
    # compose(cmd='run --rm factory', path=build_dir(''))

    env.live = False
    return True


def list_dir(path=None):
    """returns a list of files in a directory (dir_) as absolute paths"""
    dir_ = path or env.cwd
    string_ = run("for i in %s*; do echo $i; done" % dir_)
    files = string_.replace("\r", "").split("\n")
    return files


@task
def write_requirements(exclude_package: bool = True):
    """

    Args:
        exclude_package:

    Returns:

    """
    build_dir = dirify(env.build_dir, force_posix=True)
    wheels = list_dir(build_dir('wheelhouse/'))

    package = '{package}=={tag}\n'.format(package=env.project_name, tag=env.tag)

    requirements = io.StringIO()

    for wheel in wheels:
        name = os.path.basename(wheel)
        requirement = '=='.join(name.split('-', maxsplit=2)[:2]) + '\n'

        if not (exclude_package and requirement == package):
            requirements.write(requirement)

    filer(cmd='put', local_path=requirements, remote_path=build_dir('requirements.txt'))


@task
def make_default_webapp(tag: str = None, image_type: str = 'wheel', push: bool = True,
                        instance: str = None, py_version: str = '3.5') -> None:
    """Builds a docker image that contains the necessary libraries and dependencies to run the
    specified package from.

    Note:
        This task requires that the package has a setup.py file that lists all its dependencies
         in ``install_requires``. If this is not the case, an optional ``requirements.txt`` can be supplied.

    Args:
        package: The name and optional version of package to build a docker image for.
            Can be any format that is accepted by pip, including GitHub links.
        tag: The SemVer Tag
        image_type: Either immutable, wheel, or source. Immutable adds installs the target package, wheel adds ONBUILD
            commands to add a wheel file for production image and source adds ONBUILD commands for adding source
            to production image
            If the latter two are chosen it means it is a three step build process: Make wheel,
            make and publish runtime and add application for production.
        push: Whether to push image to DockerHub. Warning: do not push immutable images with proprietary code to
            DockerHub!
        instance: Sets the instance tag for immutable builds, e.g. 'production'.
        py_version: Default = 3.5. Python 3.6 is also supported.

    Returns:
        None

    """
    if tag is None:
        tag = env.tag

    build_dir = dirify(env.build_dir, force_posix=True)
    build_extension = ''

    # Uses the recipe from requirements.txt, typically just the package name
    if image_type == 'immutable':
        tag = tag + '-' + instance
        build_extension = ''
        execute('cp recipes/requirements.txt ./requirements.txt', path=build_dir(''), live=True)
    elif image_type == 'wheel':
        build_extension = '-wheel'
        write_requirements(exclude_package=True)
    elif image_type == 'source':
        build_extension = '-source'
        filer(cmd='put', local_path='./requirements.txt', remote_path=build_dir('requirements.txt'))

    execute(
        cmd='sed -e "s/PY_VERSION/{0}/g" Dockerfile{1}.template > Dockerfile{1}'.format(py_version, build_extension),
        path=build_dir(''), live=True)

    docker_tag = '{image_name}:{tag}'.format(image_name=env.image_name, tag=tag)
    docker('build -f Dockerfile{} -t {} .'.format(build_extension, docker_tag), path=build_dir(''), live=True)

    if push:
        # TODO: Allow publishing to private docker registry
        docker('tag {image_name}:{tag} {image_name}:latest'.format(
            image_name=env.image_name, path='', tag=tag), live=True)

        push_image(tag=tag, live=True)

        # TODO: Figure out a way to keep latest up to date
        push_image(tag='latest', live=True)

    # TODO: make path configurable and locally executable
    # execute('docker build -t {image_name}:{tag} .'.format(
    #     image_name=env.image_name, tag=tag), path='/srv/build', live=True)


@task
def push_image(tag: str = None, live: bool = False) -> None:
    """Wrapper to simplify pushing an image to DockerHub

    """
    if tag is None:
        tag = env.tag

    if live is None:
        live = env.live

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
def release_runtime(tag: str = None, image_type: str = 'wheel', instance: str = None,
                    py_version: str = '3.5', c_ext: bool = True) -> None:
    """Rebuilds the docker container for the python runtime and push a tag image to to DockerHub.

    Note:
        Does not affect current running webapp. This task is safe, it does not affect the production runtime!

    Args:
        tag: Name of release, preferably a SemVer version number
        image_type: See :py:func:`make_default_webapp` for options.
        instance: See :py:func:`make_default_webapp`.
        py_version: See :py:func:`make_default_webapp`.
        c_ext: See :py:func:`make_wheels`.

    Returns:
        None
    """
    env.live = True
    tag = tag or env.tag

    # Don't break of build-reqs.txt does not exist.
    use_recipe = True
    if not os.path.exists('build-reqs.txt'):
        use_recipe = False
    make_wheels(use_package=True, use_recipe=use_recipe, py_version=py_version, c_ext=c_ext, interactive=False)

    make_default_webapp(tag=tag, image_type=image_type, push=True, instance=instance, py_version=py_version)


@task
def release_code(tag: str = None, upload_wheel: bool = False, no_push: bool = False) -> None:
    """Commit, tag, push to GitHub and optionally upload wheel to dstack-factory for archiving

    Note:
        This task is safe, it does not affect the production runtime!

    Args:
        tag: Optional. Specify a SemVer compliant version code to force a specific version. (Deprecated?)
        upload_wheel: Default = False. If True, uploads wheel file to your dstack-factory for building.
        no_push: Default = False. If True, does not push tag to git repo.

    Example:
        fab e release_code:upload_wheel=True,hosts=host.name

        If successful, the next step is to run ``make_wheels``

    """

    # Only use SemVer major.minor.patch version tag for git releases
    tag = tag or '.'.join(env.tag.split('.')[:3])
    print(yellow('The current version is: {version}. The release tag will be: {tag}'.format(
        version=env.version, tag=tag)))

    if len(env.version.split('.')) == 5:
        # raise AssertionError('Git tree is dirty')
        print(red('First commit all changes, then run this task again'))
        return exit(1)
    else:
        if tag == 'latest':
            if not no_push:
                git('push origin master')
        else:
            try:
                git('tag v{tag}'.format(tag=tag))
            except SystemExit:
                print(yellow('Git tag already exists'))
            if not no_push:
                git('push origin v{tag}'.format(tag=tag))
            env.version = tag
            env.tag = tag

        execute('rm -rf dist/ build/ *.egg-info/ && python setup.py build bdist_wheel')

        if upload_wheel:
            wheel = '{package}-{tag}-py3-none-any.whl'.format(package=env.project_name, tag=env.tag)
            s3cp(simple_path='dist/' + wheel, direction='up')

            # build_dir = dirify(env.build_dir, force_posix=True)
            # filer(cmd='put', local_path=os.path.join('dist', wheel),
            #       remote_path=build_dir('archive/'), fix_perms=False)


@task
def release_data(version: str, live: bool = None) -> None:
    """Backup and upload tagged version of database

    Note:
        This task is safe, it does not affect the production runtime!

    Args:
        version: The version of the static files
        live:
        tag: Name of release, preferably a SemVer version number

    Returns:
        None

    Todo:
        * Implement S3(?) database/fixture/view storage
        * Implement cloud storage for media + static files
    """
    if live is None:
        live = env.live

    manage(cmd='collectstatic --no-input -v1 -i src -i demo -i test -i docs', live=live)
    # s3cp(simple_path='.local/static/',  s3_path='{}/static/{}'.format(env.project_name, version))
    s3(cmd='sync .local/static/ s3://dstack-storage/{}/static/{}/'.format(env.project_name, version))

    # TODO: Implement S3(?) database/fixture/view storage
    # TODO: Implement cloud storage for media + static files
    # print('Not implemented! ')
    # raise NotImplementedError


@task
def release_tag(tag: str = None) -> None:
    """Convenience task that release a named version of the runtime, code and data

    Args:
        tag: Name of release, preferably a SemVer version number

    Returns:
        None

    """
    answer = prompt('Did you update the code?', default='yes', )
    if answer == 'yes':
        release_code(tag=tag)

    answer = prompt('Did you make changes the static files?', default='no', )
    if answer == 'yes':
        release_data()

    answer = prompt('Did you update python dependencies?', default='no', )
    if answer == 'yes':
        release_runtime()
    else:
        docker('tag {image_name}:latest {image_name}:{tag}'.format(
            image_name=env.image_name, tag=env.tag), path='', live=True)
        # push_image(tag=tag, live=True)
        docker('push {image_name}:{tag}'.format(
            image_name=env.image_name, tag=env.tag), path='', live=True)


@task
def build_runtime(image_name: str = None, tag: str = None, instance: str = 'production',
                  use_wheel: bool = False, live: bool = None) -> None:
    """Builds the production runtime

    This task is safe, it does not affect the running instance!
    The next restart, however, might change the runtime.

    TODO:
        Rewrite.

    """
    tag = tag or env.tag
    image_name = image_name or env.image_name

    # Pull latest docker version
    answer = prompt('Did you update the base image?', default='no', )
    if answer == 'yes':
        docker('pull {image_name}:{tag}'.format(image_name=image_name, tag=tag), live=live)
        docker('pull {image_name}:latest'.format(image_name=image_name), live=live)
        # docker('tag {image_name}:{tag} {image_name}:latest'.format(
        #     image_name=image_name, tag=tag), live=True)

    if env.live:
        git('fetch --all', live=True)
        answer = prompt('Checking out a tag?', default='yes', )
        if answer == 'yes':
            git('checkout --force v{tag}'.format(tag=tag), live=True)
        else:
            git('checkout --force origin/master', live=True)

    # execute("rsync -avz --exclude-from '.dockerignore' ./src/ .local/build/", live=True)

    docker('tag {image_name}:{tag} default_webapp'.format(
        image_name=image_name, tag=tag), path='', live=live)

    if use_wheel:
        # TODO: Update/create/install virtualenv/python?
        execute('rm -rf dist/ build/ {project_name}.egg-info/ && python setup.py build bdist_wheel'.format(
            project_name=env.project_name), live=live)
        # execute('')

    # TODO: Figure out consecquences, e.g follow up tasks
    env.tag = tag
    compose('build webapp', instance=instance, live=live)


@task
def deploy_runtime(tag: str = None, instance: str = 'production', first: bool = False) -> None:
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
    # This task is designed to only run on server
    env.live = True

    # Either use current git version or the specified version
    tag = tag or env.tag

    env.tag = tag

    if first:
        compose('up -d webapp', instance=instance)
        manage('migrate')
        # TODO: understand how fixtures are namespaced and loaded to avoid specifying paths
        manage('loaddata config/fixtures/initial_data.json')

    else:
        answer = prompt('Did you want to migrate?', default='no', )

        if answer == 'yes':
            answer = prompt('Do you want to create a backup?', default='yes', )
            if answer == 'yes':
                postgres(cmd='backup', tag=tag + '-rollback')
            manage('migrate', live=True)
            answer = prompt('Was the migration successful?', default='yes', )
            if answer == 'no':
                postgres(cmd='restore', tag=tag + '-rollback')
                raise Exception('Deployment failed')

    compose('up -d webapp')

    with prefix('export UID'):
        # compose('up static_builder')
        compose('up static_collector')
        compose('up volume_fixer')


@task
def deliver(tag: str = None, instance: str = 'production', image_name: str = None, first: bool = False, use_wheel: bool = False) -> None:
    """From build to deploy!

    Main task for delivering a new task to the server.

    Args:
        tag: Preferably a SemVer version number, e.g. 1.2.10.
            Used to identify the git tag, docker tag and database backup tag.
        instance: Distinguishes the final immutable image from the base image. e.g. 1.2.10-production.
        image_name: Used to override the image_name retrieved from the env dict.
        first: Initialize the project if True, otherwise update it.
        use_wheel: Whether to use requirements.txt or pre-build wheel file.

    """
    release_tag(tag=tag)

    if first:
        init_deploy()
        copy_envs()

    build_runtime(image_name=image_name, tag=tag, instance=instance, use_wheel=use_wheel)
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
def init_deploy(ssh: bool = False):
    """Task for initialising webapps deployed for the first time.

    Args:
        ssh: Use ssh style GitHub cloning if True, https style if False

    Returns:
        None

    Todo:
        Make distinction between project name and GitHub name. Also allow other git repos/hosts

    """
    env.live = True

    if ssh:
        git(cmd='clone git@github.com:{}/{}.git {}'.format(env.organisation, env.git_repo, env.project_name),
            path='/srv/apps')
    else:
        git(cmd='clone https://github.com/{}/{} {}'.format(env.organisation, env.git_repo, env.project_name),
            path='/srv/apps')

    execute('mkdir -p .local')
    execute('mkdir -p src/static')

    # TODO: Make this work. Maybe check out dockergen templating or add to server install
    execute('cp /srv/nginx/templates/nginx-vhost.conf /srv/nginx/vhost.d/{}'.format(env.virtual_host), path='')
    execute("sed -i.bak 's/{{project_name}}/%s/g' '/srv/nginx/vhost.d/%s'" % (
        env.project_name.replace('.', '\.'), env.virtual_host), path='')

    env.live = False

# @task
# def copy_envs():
#     put('.local/*', '/srv/apps/{}/.local/'.format(env.project_name))


# INSTALL Virtualenv kernel python:
# OUTDATED but with correct path to copy:
# http://help.pythonanywhere.com/pages/IPythonNotebookVirtualenvs

# Correct usage:
# https://github.com/ipython/ipykernel/issues/52#issuecomment-212001601

@task
def new_release():
    # TODO: What happens when runtime updated?

    project_dir = dirify(env.project_dir, force_posix=True)

    execute('rm -rf {}'.format(project_dir('dist/*.whl')), live=True)
    filer(cmd='put',
          local_path='dist/{}-{}-py3-none-any.whl'.format(env.project_name, env.tag),
          remote_path=project_dir('dist'))

    dotenv(action='set', key='VERSION', value=env.tag, live=True)
    dotenv(action='set', key='VERSION', value=env.tag, env_file='.local/webapp.env', live=True)

    compose('build webapp',  path=env.project_dir, live=True)
    compose('up -d webapp',  path=env.project_dir, live=True)
