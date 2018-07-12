from invoke import Collection

from .base import do, dry, e, echo, t1, t2
from .factory import make_wheels, release_runtime
from .tasks import deploy, release_code, test, release_superset, local_build, db, create_backup_table, full_db_test
from .wrap import bash, compose, docker, filer, git, mysql, postgres, s3cmd, python

ns = Collection()

ns.add_task(e)
ns.add_task(echo)
ns.add_task(dry)
ns.add_task(bash)

ns.add_task(s3cmd)
ns.add_task(git)
ns.add_task(python)
ns.add_task(docker)
ns.add_task(compose)
ns.add_task(postgres)
ns.add_task(mysql)

ns.add_task(test)
ns.add_task(release_code)
ns.add_task(deploy)
ns.add_task(release_superset)
ns.add_task(local_build)
ns.add_task(db)
ns.add_task(create_backup_table)
ns.add_task(full_db_test)

ns.add_task(t1)
ns.add_task(t2)

factory = Collection('factory')
factory.add_task(make_wheels)
factory.add_task(release_runtime)
ns.add_collection(factory)
