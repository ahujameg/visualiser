# Visualiser
This is a web application for handling visualisation for HGQN.  

### Pre-requisites:
This application works with python version 3.10, make sure it is installed or use the following command to install it:
```
sudo apt update
sudo apt install python3
```

Install pip3:
``` 
sudo apt install pip3 
```

Then, install Pipenv. Pipenv is a tool that provides all necessary means to create a virtual environment for a 
Python project. It automatically manages project packages through the Pipfile file as packages are installed or uninstalled:
```
pip3 install pipenv
```

### Install requirements
To run the django application, first set the environment using the pipfile:
```
pipenv shell
```
Install the requirements:
```
pipenv sync
```
Alternatively, if you are unfamiliar with pipenv you can use the requirements.txt file to install required packages.
```
pip3 install -r requirements.txt
```
### Update secret-key

Generate a Django secret key using following command:
```
python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Paste the newly generated key in the DJANGO_SECRET_KEY enviornment variable in the 
visualiser\settings.py file which contains the following line:
```commandline
SECRET_KEY = env("DJANGO_SECRET_KEY", default="ChangeMe!!")
```

### Application Startup
Start the application server on a different port other than the port used by the the parent application like Varfish, for example on port 7000:
```
python3 manage.py runserver 7000
```

## Docker setup:
Visualiser application can be started in the docker container using the following steps.

Make sure Docker is installed, you can use the steps mentioned here to install Docker - https://docs.docker.com/engine/install/ 
1. Build the docker image
    ```
    sudo docker build -t visualiser-app .
    ```
2. Run the image in a docker container
    ```
    sudo docker run -p 7000:7000 visualiser-app
    ```

### Starting other services with Docker compose

#### HGQN service
 Add description here

### Send data through Visualiser
1. Launch the Visualiser server in a browser at http://127.0.0.1:7000
2. Click on 'Choose Data' button and send it to the HGQN application.
3. ...Add more steps here..

