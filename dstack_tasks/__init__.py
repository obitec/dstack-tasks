from .checkup import doctor
from .utils import dirify, get_result, vc
from .wrappers import docker, compose, manage, pip, bower, npm, git, postgres, conda, dotenv, execute, filer, s3,\
    docker_exec
from dstack_tasks.helpers import echo
from dstack_tasks.wrappers import dry
from .deploy import make_wheels, make_default_webapp, push_image, snapshot, rollback, ci, build

# improved workflow
from .deploy import release_code, release_data, build_runtime, deploy_runtime, release_tag, release_runtime, build_code

# Config setup related
from .tasks import e, fabric_setup, local_setup, remote_setup, postgres_everywhere, init

# Untested
from .tasks import backup_basics, clean_unused_volumes, sqlite_reset, reset_local_postgres, restore_latest_postgres, \
    translate, datr, container_reset

# Local
from .local import init

# Deprecated
from .tasks import upload_www, upload_config, upload_app, deploy

from .helpers import echo
from dstack_tasks import dry
