import io
import os

import colorama
from invoke import task

from .base import do, env
from .utils import dirify
from .wrap import compose, docker, filer, s3cmd

colorama.init()


@task
def make_wheels(ctx, use_package=None, use_recipe=None, clear_wheels=True,
                interactive=True, py_version='3.6', c_ext=True):
    """Build wheels for python packages

    Creates wheel package for each dependency specified in build-reqs.txt (if it exists) else
    relies on the main packages's setup.py file to find and build dependencies.

    Args:
        ctx: Task context.
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

    package = ctx.project_name
    tag = env.tag

    # Set the defaults
    build_directory = dirify('/srv/build/', force_posix=True)
    recipe_filename = 'requirements'

    # If neither parameters are given, use defaults for both (same as specifying True for both)
    if use_package is None and use_recipe is None:
        use_package = True
        use_recipe = True

    if use_package in [True, 'True', 'true', '1']:
        use_package = f'{package}-{tag}-py3-none-any.whl'
    if use_recipe in [True, 'True', 'true', '1']:
        use_recipe = 'build-reqs.txt'

    # This is the default way of building runtime images:
    # The .whl file created from "setup.py build bdist_wheel" will be used to get list of dependencies
    # dstack-factory will use the "install_requires" to determine what dependencies to create wheel files for.
    # This method works best if your dependencies are all released on pip
    if use_package and use_recipe:
        # Naive check to see if a matching .whl file has recently been built
        # TODO: test if it has actually been uploaded to archive and optionally download from s3cmd or upload if not
        wheel_file = f'{package}-{tag}-py3-none-any.whl'
        if not os.path.exists('dist/' + wheel_file):
            # raise AttributeError(
            #     'Trying to build wheels from project wheel, but build does not exist')
            print(colorama.Fore.RED + f'ERROR: First build your file. {wheel_file} does not exist.')
            return exit(1)

        # Two step build process:
        # 1. Build wheels from the build-reqs.txt file
        make_wheels(ctx, use_recipe=use_recipe, interactive=False)
        # 2. Don't clear wheel files, build using wheel file uploaded.
        make_wheels(ctx, use_package=use_package, clear_wheels=False, interactive=False)
        return True

    # Useful for something like superset that can be installed from pip or from arbitrary wheel file uploaded archive.
    # There is currently now difference between specify a .whl file or a pip package specification except that it
    # asks you if you've uploaded the file to the archive. This is because when dstack-factory builds wheels it checks
    # for existing wheels in archive before downloading from pip or other source.
    elif use_package and not use_recipe:
        # TODO: Also add support for s3cmd hosted .whl files, e.g. s3cmd://dstack-storage/django-1.10.3-py3-none-any.whl
        # print(use_package[-4:])
        if use_package[-4:] == '.whl':
            # e.g. make_wheels(use_package='django-1.10.3-py3-none-any.whl')
            if interactive:
                answer = input('Did you remember to upload wheel package to dstack-factory archive?')
            else:
                answer = 'no'

            package, tag = use_package.split('-', maxsplit=2)[:2]
            use_recipe = io.StringIO(f'{package}=={tag}')

            if answer == 'no':
                wheel = 'f{package}-{tag}-py3-none-any.whl'

                # try:
                s3cmd(simple_path=f'dist/{wheel}', local_path=build_directory('archive/'), direction='down')
                # except Exception:
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
            recipe_filename = f'{ctx.project_name}-{env.tag}'
        else:
            # raise FileNotFoundError('Recipe file not found!')
            print(colorama.Fore.RED + 'Warning: Recipe file does not exist')
            # return exit(1)

    else:
        print(colorama.Fore.RED + 'Invalid setup. Must specify either use_package, or use_recipe')
        return exit(1)

    if clear_wheels:
        do(ctx, cmd='rm -rf *.whl', path=build_directory('wheelhouse'))

    # Copy the recipe string to S3
    filer(content=use_recipe, key=f'factory/recipes/{recipe_filename}.txt', dry_run=env.dry_run)

    # Copy the recipe from s3 to server
    s3cmd(ctx, local_path=build_directory(f'recipes/{recipe_filename}.txt'),
          s3_path=f'factory/recipes/{recipe_filename}.txt',
          direction='down')

    do(ctx,
       cmd=f'export RECIPE={recipe_filename} PY_VERSION={py_version} CEXT={c_ext} && docker-compose run --rm factory',
       path=build_directory(''))
    # compose(cmd='run --rm factory', path=build_directory(''))

    return True


@task
def release_runtime(ctx, build_wheels=True, build_image=True, tag=None):
    """

    Args:
        ctx:
        build_wheels:
        build_image:
        tag:

    """
    # TODO: Indicate that this task must be run with a host configured
    # TODO: Make wheel-factory configurable
    factory_host = 'gauseng.apps'
    tag = tag or ctx.tag

    if build_wheels:
        # Stage 0: Clear the wheelfiles
        do(ctx, cmd='rm -rf *.whl', path='/srv/build/wheelhouse')

        # TODO: Get from environment
        project_name = os.path.basename(os.getcwd()).replace('-', '_')
        s3cmd(ctx,
              s3_path=f'{project_name}/dist/{project_name}-{tag}-py3-none-any.whl',
              local_path='/srv/build/wheelhouse/',
              direction='down',
              project_name=project_name)

        # Stage 1: build-reqs.txt
        # scp build-reqs.txt gauseng.apps:/srv/build/recipes/toolset-0.18.4.txt
        # scp "toolset==0.18.4" gauseng.apps:/srv/build/recipes/requirements.txt
        # BUILD WHEELS
        do(ctx, cmd=f'scp build-reqs.txt {factory_host}:/srv/build/recipes/{project_name}-{tag}.txt', local=True)

        compose(ctx, cmd='run --rm factory', path='/srv/build',
                env={'RECIPE': f'{project_name}-{tag}', 'PY_VERSION': '3.6', 'CEXT': 'True'})

        # Stage 2: Upload wheel file and build from there
        # aws s3 cp s3://dstack-storage/toolset/dist/toolset-0.18.4-py3-none-any.whl /srv/build/archive/
        # scp "amqp==2.1.4 ...." gauseng.apps:/srv/build/requirements.txt
        # BUILD WHEELS
        # compose(ctx, cmd='run --rm factory', path='/srv/build',
        #         env={'RECIPE': 'requirements.txt', 'PY_VERSION': 3.6, 'CEXT': True})
        # do(ctx, cmd=f'echo toolset-{ctx.tag} > /srv/build/recipes/requirements.txt')
        #
        # compose(ctx, cmd='run --rm factory', path='/srv/build',
        #         env={'RECIPE': f'requirements', 'PY_VERSION': 3.6, 'CEXT': True})

    if build_image:
        # Stage 3:
        # Build docker image and install all the wheel in the directory.
        # docker build -f Dockerfile-wheel -t obitec/ngkdb:2.0.4 .
        docker_tag = f'{ctx.organisation}/{ctx.project_name}'
        docker(ctx, cmd=f'build -f Dockerfile-wheel -t {docker_tag}:{tag} .', path='/srv/build')
        # docker tag obitec/ngkdb:2.0.4 obitec/ngkdb:latest
        docker(ctx, cmd=f'tag {docker_tag}:{tag} {docker_tag}:latest')
        # docker push obitec/ngkdb:latest
        docker(ctx, cmd=f'push {docker_tag}:{tag}')
        docker(ctx, cmd=f'push {docker_tag}:latest')
