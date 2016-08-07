from fabric.colors import yellow, red
from fabric.context_managers import cd, prefix
from fabric.decorators import task
from fabric.operations import put, run, prompt, local
from fabric.state import env

from dstack_tasks import dirify, compose, docker, postgres, manage, execute, vc


@task
def make_wheels() -> None:
    """

    :return:
    """

    build_dir = dirify(env.build_dir, force_posix=True)

    put('./etc/build-requirements.txt', build_dir('build-requirements.txt'))

    with cd(build_dir('wheelhouse')):
        run('rm -rf *.whl')

    compose(cmd='-f service.yml -p %s run --rm wheel-factory' % env.project_name, path=build_dir(), live=True)


@task
def make_default_webapp() -> None:
    put('./requirements.txt', '/srv/build/requirements.txt')

    with cd('/srv/build'):
        run('docker build -t {image_name} .'.format(
            image_name=env.image_name,
        ))


@task
def push_image(tag: str = 'latest', live: bool = False) -> None:
    """

    :param tag:
    :param live:
    :return:
    """
    docker('push %s:%s' % (env.image_name, tag), live=live)


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
    """

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
