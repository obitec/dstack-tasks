============
Contributing
============

1. Clone this repository:


.. code-block:: bash

    git clone https://github.com/obitec/dstack-tasks
    cd dstack-tasks

1. Create a python virtual environment and activate:


.. code-block:: bash

    python3.5 -m venv venv
    source venv/bin/activate

2. Update pip and install development dependencies:


.. code-block:: bash

    pip install -U pip
    pip install -e .[dev]

3. Build the app and docs:


.. code-block:: bash

    invoke build --docs

4. Create a pull request :-)
