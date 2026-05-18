#!/bin/sh
set -e

python manage.py migrate --noinput --fake-initial
python manage.py runserver 0.0.0.0:80
