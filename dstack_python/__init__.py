from invoke import Collection

from .wrap import git, docker, compose, s3, postgres, mysql
from .tasks import release, deploy, deploy_static, test
from .base import dry, do
from . import wrap
from . import tasks

# local = Collection('local')
# local.add_task(release)

ns = Collection()
# ns.add_collection(local)

ns.add_task(dry)

ns.add_task(s3)
ns.add_task(git)
ns.add_task(docker)
ns.add_task(compose)
ns.add_task(postgres)
ns.add_task(mysql)


ns.add_task(test)
ns.add_task(release)
ns.add_task(deploy)
ns.add_task(deploy_static)
