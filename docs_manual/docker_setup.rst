.. _docker_setup:

======================
Docker Setup
======================

visualiser application can be started in the docker container using the following steps.

.. note::

    Make sure Docker is installed, you can use the steps mentioned here to install Docker - https://docs.docker.com/engine/install/

1. Build the docker image

    .. code-block:: console

        $sudo docker build -t visualiser-app .

2. Run the image in a docker container

    .. code-block:: console

        $sudo docker run -p 7000:7000 visualiser-app

-------------------------------------------
Starting other services with Docker compose
-------------------------------------------


HGQN service
======================

To run the HGQN service, get the code and follow the steps mentioned here:
addLinkHere

Build the docker image
    .. code-block:: console

        $sudo docker build -t gm-api .


HGQN service
======================
To run the HGQN service, get the code and follow the steps mentioned here:
https://addLinkHere

Build the docker image
    .. code-block:: console

        $sudo docker build -t pedia-classifier-api .


Run Docker-compose
======================

Once the images of the services are ready, run the following command to start all of them in docker container.
    .. code-block:: console

        $sudo docker-compose up
