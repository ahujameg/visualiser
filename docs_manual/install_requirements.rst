.. _install_requirements:

======================
Install Requirements
======================

To run the django application, first set the environment using the pipfile:

.. code-block:: console

    $pipenv shell

Install the requirements:

.. code-block:: console

    $pipenv sync

Alternatively, if you are unfamiliar with pipenv you can use the requirements.txt file to install required packages.

.. code-block:: console

    $pip3 install -r requirements.txt

Update Secret-key
==================

Generate a Django secret key using following command:

.. code-block:: console

    $python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

Paste the newly generated key in the DJANGO_SECRET_KEY enviornment variable in the
visualiser\settings.py file which contains the following line:

.. code-block:: python

    SECRET_KEY = env("DJANGO_SECRET_KEY", default="ChangeMe!!")

