Notes
=====

For configuring PyCharm to work with Docker for Mac, see: https://kawashi.me/docker-integration-in-pycharm-when-using-docker-for-mac.html

Basically::

    brew install socat
    socat TCP-LISTEN:2375,reuseaddr,fork,bind=localhost UNIX-CONNECT:/var/run/docker.sock &

and then add a docker server in Pycharm using::

    tcp://localhost:2375

