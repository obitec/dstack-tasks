.. Django FactBook documentation master file, created by
   sphinx-quickstart on Sun May 22 17:34:01 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to DStack Tasks' documentation!
=======================================

Contents:

.. toctree::
   :maxdepth: 2

   contributing
   modules/models

========
Overview
========

Part of the DStack project. This package provides the utilities and tasks that make it easier to
develop, build and deploy dockerized Django apps.


Quick start
-----------

1. Install the library::

    pip install -U git+https://github.com/obitec/dstack-tasks

2. Import the package at the top of your project's fabfile::

    # fabfile.py
    from dstack_tasks import *

3. Run the doctor task to check if everything is okay::

    fab doctor

4. Create a project.yml and/or .env file to configure your tasks::

    # project.yml
    project:
      name: example
      version: 0.9.9
      maintained_by:
        - name: A Thor
          email: e@mail.com
      description: "How awesome is your project?"

    # .env
    HOST_NAME=example_host
    VIRTUAL_ENV=example_env
    PROJECT_NAME=example_name

5. Happy coding :-)


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

