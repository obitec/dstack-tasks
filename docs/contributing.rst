============
Contributing
============

1. Clone this repository::

    git clone https://github.com/obitec/dstack-tasks
    cd dstack-tasks

1. Create a python virtual environment and activate::

    pyvenv-3.5 venv
    . venv/bin/activate

2. Update pip and install development dependencies::

    pip install -U pip
    pip install -e .[dev]

3. Build the app and docs::

    invoke build --docs

4. Create a pull request :-)
