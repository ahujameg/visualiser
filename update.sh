#!/bin/sh
git pull
pip install -r requirements.txt
ps aux |grep gunicorn | grep -v grep | awk '{print $2}' | xargs kill -HUP

