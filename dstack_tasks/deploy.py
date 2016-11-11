from fabric.colors import yellow, red
from fabric.context_managers import prefix
from fabric.decorators import task
from fabric.operations import prompt, local
from fabric.api import env

from .wrappers import compose, docker, postgres, manage, execute, git
from .utils import dirify, vc

@task
def make_wheels() -> None:
    """

    :return:
    """

    build_dir = dirify(env.build_dir, force_posix=True)

    # put('./{}'.format(require_dir),
    #     build_dir('build-requirements.txt'))

    execute('rm -rf *.whl', path=build_dir('wheelhouse'), live=True)

    compose(cmd='-f service.yml -p %s run --rm wheel-factory' % env.project_name, path=build_dir(''), live=True)


@task
def make_default_webapp(tag: str = 'latest') -> None:
    # put('./requirements.txt', '/srv/build/requirements.txt')

    # TODO: make path configurable and locally executable
    execute('docker build -t {image_name}:{image_tag} .'.format(
        image_name=env.image_name, image_tag=tag), path='/srv/build', live=True)


@task
def push_image(tag: str = 'latest', live: bool = False) -> None:
    """

    :param tag:
    :param live:
    :return:
    """
    docker('push %s:%s' % (env.image_name, tag), path='', live=live)


@task
def snapshot(live: bool = False, tag: str = 'tmp') -> None:
    """

    :param live:
    :param tag:
    :return:
    """

    # if tag == 'tmp':
    #     release = prompt('Please supply a release name', validate=r'^\w+-\d+(\.\d+)?$')

    answer = prompt('Did you remember to first commit all changes??', default='no', )
    if answer == 'yes':
        try:
            local('git tag %s' % tag)
        except SystemExit:
            print(yellow('Git tag already exists'))

        postgres('backup', live=live, tag=tag)

        try:
            docker('tag {image_name}:latest {image_name}:{tag}'.format(
                image_name=env.image_name, tag=tag))
            docker('tag {image_name}:production {image_name}:{tag}-production'.format(
                image_name=env.image_name, tag=tag))
        except SystemExit:
            print(red('Docker image :latest not found'))

    else:
        print("# Commit changes using:\n$ git commit -a -m 'message...'")


@task
def rollback(live: bool = False, tag: str = 'tmp') -> None:
    """

    :param live:
    :param tag:
    :return:
    """
    answer = prompt('Did you remember to first release?', default='no', )
    # print(answer)
    if answer == 'yes':
        local('git branch development')
        local('git reset --hard %s' % tag)
        postgres('restore', live=live, tag=tag)
        docker('tag {image_name}:{tag} {image_name}:latest'.format(
            image_name=env.image_name, tag=tag))
    else:
        print("# You can do a release by running:\n$ fab release:tag='tag'")


@task
def ci(tag: str) -> None:
    """

    :param tag:
    :return:
    """
    snapshot(tag=tag + '-development', live=False, )
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
        local("sed -i .bak 's/RELEASE_TAG.*/RELEASE_TAG=%s/g' '.env'" % tag)
        # deploy()
        build(live=True)
        # postgres(cmd='restore', tag=tag + '-staging', live=True)
        manage('migrate', live=True)
        compose(cmd='up -d', live=True)

        answer = prompt('Did the app successfully update?', default='yes', )
        if answer == 'yes':
            snapshot(tag=tag, live=True)
            push_image(tag=tag, live=True)

        print('Successfully deployed app %s!' % tag)


@task
def build(live: bool = False) -> None:
    """
    DEPRECTED: See deploy_runtime
    :param live:
    :return:
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
    """DEPRECATED, please see build_runtime

    :param live:
    :param migrate:
    :return:
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
    """
    Rebuilds the docker container for the python runtime and push a tag image to to DockerHub.
    Does not affect current running webapp

    This task is safe, it does not affect the production runtime!

    :param tag: Name of release, preferably a SemVer version number
    :return:
    """

    make_wheels()
    make_default_webapp(tag=tag)
    # TODO: should be able to specify private repo

    # docker('tag {image_name}:{tag} {image_name}:latest'.format(
    #     image_name=env.image_name, tag=tag), live=True)

    push_image(tag=tag, live=True)

    # TODO: Figure out a way to keep latest up to date
    # push_image(tag='latest', live=True)


@task
def release_code(tag: str = 'latest') -> None:
    """
    Commits, tags and pushes tag to GitHub

    This task is safe, it does not affect the production runtime!

    :param tag: Name of release, preferably a SemVer version number
    :return:
    """
    # TODO: Replace with actually checking for clean tree
    answer = prompt('Did you remember to first commit all changes??', default='no', )
    if answer == 'yes':
        if tag == 'latest':
            git('push origin master')
        else:
            try:
                local('git tag %s' % tag)
            except SystemExit:
                print(yellow('Git tag already exists'))
            git('push origin {tag}'.format(tag=tag))


@task
def release_data(tag: str = 'latest') -> None:
    """
    Backup and upload tagged version of database

    This task is safe, it does not affect the production runtime!

    :param tag: Name of release, preferably a SemVer version number
    :return:
    """
    # TODO: Implement S3(?) database/fixture/view storage
    # TODO: Implement cloud storage for media + static files
    print('Not implemented! ' + tag)

    # raise NotImplementedError


@task
def release_tag(tag: str = 'latest') -> None:
    """
    Convenience task that release a named version of the runtime, code and data

    :param tag: Name of release, preferably a SemVer version number
    :return:
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
        # else:
        #     docker('tag {image_name}:latest {image_name}:{tag}'.format(
        #         image_name=env.image_name, tag=tag), live=True)


@task
def build_runtime(tag: str = 'latest', image_name: str = None) -> None:
    """
    Builds the production runtime

    This task is safe, it does not affect the running instance! The next restart, however, might change the runtime

    :return:
    """
    image_name = image_name if image_name else env.image_name

    # Pull latest docker version
    answer = prompt('Did you update the base image?', default='no', )
    if answer == 'yes':
        docker('pull {image_name}:{image_tag}'.format(image_name=image_name, image_tag=tag), live=True)
        docker('tag {image_name}:{tag} {image_name}:latest'.format(
            image_name=image_name, tag=tag), live=True)

    git('fetch --all', live=True)
    answer = prompt('Checking out a tag?', default='yes', )
    if answer == 'yes':
        git('checkout --force {tag}'.format(tag=tag), live=True)
    else:
        git('checkout --force origin/master', live=True)

    # execute("rsync -avz --exclude-from '.dockerignore' ./src/ .local/build/", live=True)

    env.image_tag = tag + '-production'
    # with prefix('export UID'):
    docker('tag {image_name}:{tag} default_webapp'.format(
        image_name=image_name, tag=tag), live=True)

    compose('build webapp', live=True)


@task
def deploy_runtime(tag: str = 'latest', first: bool = False) -> None:
    """
    Deploys production runtime.

    This function is not safe and requires a database
    backup before running!

    :return:
    """

    env.image_tag = tag + '-production'

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

    env.image_tag = tag + '-production'
    compose('up -d webapp', live=True)

    with prefix('export UID'):
        env.image_tag = tag
        # compose('up static_builder', live=live)
        compose('up static_collector', live=True)
        compose('up volume_fixer', live=True)
