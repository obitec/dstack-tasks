dstack-tasks
------------

dstack-tasks is a collection of invoke tasks that wrap common tools and services to make it easier to deploy code.

Tools wrapped::

    - docker
    - docker-compose
    - postgresql (backup and restore)
    - mysql (backup and restore)
    - awscli (s3 only for now)
    - git
    - python
    - django manage.py

The tasks are designed to run as a standalone console script (dstack) or as a collection of tasks to build on in
your invoke and fabric2* tasks.

Installation
------------

To install, use pip::

    pip install --pre dstack-tasks


Once installed, you can use it from within your project directory. The console script uses a `.env`
file to configure itself. At the moment, some tasks still require environmental variables before it can be used.

Example usage
-------------

To see list of tasks, use `dstack --list`. To see the help text of each task, use `dstack <task name> --help`. See below
for example usage::

    # Backs-up database
    dstack postgres backup --tag local-dev

    # Release new version of app and publish to S3 (requires ~/.aws/credentials to be set up
    dstack release_code --upload --not-static

dstack-tasks can also be used as a base library for your `invoke` and `fabric2` tasks::

    pip install https://github.com/fabric/fabric/archive/v2.zip

All tasks can be run in "dry" mode or in a specific environment. To see what a tasks will execute, run it in `dry`
mode::

    dstack dry postgres backup

To give your task additional context, you can use the special `e` task to load environmental variables
from a `.env` file::

    dstack e release_code

This can be used to for example specify a different Github repo etc.

Notes
-----

It is important to note that dstack-tasks is console script build on top of invoke and is thus primarily meant for
executing tasks locally. However, dstack-tasks fully supports being used as a library in your fabric (version 2)
fabfile.py. Simply import all tasks from `dstack_tasks` in your fabfile and you can execute them on a remote server
using something like `fab -H example.com e deploy --version 1.0.0`.

At it's core however, invoke just wraps bash commands and executes them on the server. This means that for advanced uses
it might be worthwhile to install dstack-tasks on the server to allow complex tasks to be written in python instead of
bash. So, instead of running `ls -al` via fabric 2 on the remote server and trying to capture and parse the output, you
can use an appropriate python package to get a list of files in a directory.

Known Issues
------------

dstack-tasks does not yet include a generic task that can be used to call itself on the server. There is also currently
an issue with setting runtime environmental variables using Fabric2 to run tasks remotely.
