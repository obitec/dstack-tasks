dstack-tasks
------------

Tasks for deploying code to server.

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

..code-block::

    pip install https://github.com/fabric/fabric/archive/v2.zip
    pip install --pre dstack-tasks


Once installed, you can use it from within your project directory. The console script uses a `.env`
file to configure itself. At the moment, some tasks still require environmental variables before it can be used.


Example usage
-------------

To see list of tasks, use `dstack --list`. To see the help text of each task, use `dstack <taskname> --help`. See below
for example usage:

..code-block::
    # Backs-up database
    dstack postgres backup --tag local-dev

    # Release new version of app and publish to S3 (requires `~/.aws/credentials` to be set up
    dstack release_code --upload --not-static
