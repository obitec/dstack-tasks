from fabric.decorators import task

from dstack_tasks import docker


@task
def init():
    docker('volume create --name=nginx_media')
    docker('volume create --name=nginx_static')
    docker('network create nginx_proxy')
