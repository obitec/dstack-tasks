Notes
=====

For configuring PyCharm to work with Docker for Mac, see: https://kawashi.me/docker-integration-in-pycharm-when-using-docker-for-mac.html

Basically:

.. code-block:: bash

    brew install socat
    socat TCP-LISTEN:2375,reuseaddr,fork,bind=localhost UNIX-CONNECT:/var/run/docker.sock &

and then add a docker server in Pycharm using:

.. code-block:: bash

    tcp://localhost:2375


Advanced docker filtering:

.. code-block:: bash

   docker ps --filter "status=exited" | grep '2 days ago' | awk '{print $1}' | xargs --no-run-if-empty docker rm

from http://stackoverflow.com/questions/17236796/how-to-remove-old-docker-containers
