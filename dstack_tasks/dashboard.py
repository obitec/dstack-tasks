import os

from fabric.api import task, prompt, put, settings, hide, env

from .wrappers import docker_exec, docker, execute


@task
def install_dashboard():
    docker_exec(service='dashboard', cmd='fabmanager create-admin --app caravel')
    docker_exec(service='dashboard', cmd='caravel db upgrade')
    docker_exec(service='dashbpard', cmd='caravel init')


@task
def sync_caravel(live=True):
    answer = prompt('This destroys all changes on server! Continue?', default='no', )
    if answer == 'yes':
        put('bin/caravel-sync.sh', os.path.join(env.project_dir, 'var/backups/caravel/sync.sh'))
        docker('cp {pd}/var/backups/caravel {project}_postgres_1:/backup'.format(
            pd=env.project_dir, project=env.project_name), live=live)
        docker_exec(service='postgres', cmd='bash -c "cd /backup/caravel && ./sync.sh"', live=live)


@task
def dump_caravel(live=False):
    with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        out = execute(
            'docker exec -it {project}_postgres_1 bash -c '
            '"pg_dump -U postgres -d postgres --column-inserts --data-only --table=tables"'.format(
                project=env.project_name),
            live=live
        )
        print(out)


@task
def update_views(live: bool = False, migrate: bool = False):
    execute('git pull', live=live)
    docker('cp db_views.sql {project}_postgres_1:/opt/'.format(project=env.project_name), live=live)
    docker_exec(service='postgres', cmd='psql -U postgres -f /opt/db_views.sql', live=live)
