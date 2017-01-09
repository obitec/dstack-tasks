from invoke import Collection

from .base import do, dry, e, echo, t1, t2
from .develop import build
from .factory import make_wheels, release_runtime
from .notify import send_alert, send_mail
from .remote import install_dstack_bot
from .server import create_ssh_config, machine_create, machine_info, machine_status
from .tasks import create_backup_table, db, deploy_code, full_db_test, release_code, release_superset, test
from .wrap import bash, compose, docker, filer, git, machine, mysql, python, s3cmd

ns = Collection()

ns.add_task(e)
ns.add_task(echo)
ns.add_task(dry)
ns.add_task(bash)

ns.add_task(build)

ns.add_task(s3cmd)
ns.add_task(git)
ns.add_task(python)
ns.add_task(docker)
ns.add_task(compose)
ns.add_task(machine)
ns.add_task(mysql)

ns.add_task(test)
ns.add_task(release_code)
ns.add_task(deploy_code)
ns.add_task(release_superset)
ns.add_task(db)
ns.add_task(create_backup_table)
ns.add_task(full_db_test)

# notify
ns.add_task(send_alert)
ns.add_task(send_mail)

ns.add_task(install_dstack_bot)

# server
machine = Collection('server')
machine.add_task(machine_create)
machine.add_task(machine_info)
machine.add_task(machine_status)
machine.add_task(create_ssh_config)
ns.add_collection(machine)

factory = Collection('factory')
factory.add_task(make_wheels)
factory.add_task(release_runtime)
ns.add_collection(factory)

# ns.add_task(t1)
# ns.add_task(t2)
