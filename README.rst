============
DStack Tasks
============

Part of the DStack project. This package provides the utilities and tasks that make it easier to
develop, build and deploy dockerized Django apps.

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Install the library:

.. code-block:: bash

    pip install dstack-tasks

2. Import the package at the top of your project's fabfile:

.. code-block:: bash

    # fabfile.py
    from dstack_tasks import *

3. Run the doctor task to check if everything is okay:

.. code-block:: bash

    fab e doctor

4. Create a .env file to configure your tasks:

.. code-block:: bash
   # .env

   # Optional. By default uses directory name
   PROJECT_NAME=dstack_tasks
   VIRTUAL_ENV=dstack_tasks
   IMAGE_NAME=obitec/dstack-tasks

   # Host as defined in .ssh/config
   HOST_NAME=obitec.dstack

   # Used when initialising project from GitHub:
   ORGANISATION=obitec

   SUB_PATH=/

5. Test if env file is read correctly:

.. code-block:: bash

    fab e echo


6. Happy coding :-)
