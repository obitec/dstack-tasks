from invoke import Collection

from .wrap import git, docker, compose, s3
from .tasks import release, deploy, deploy_static
from .base import dry
from . import wrap
from . import tasks

# local = Collection('local')
# local.add_task(release)

ns = Collection()
# ns.add_collection(local)

ns.add_task(dry)
ns.add_task(release)
ns.add_task(deploy)
ns.add_task(deploy_static)
ns.add_task(s3)
