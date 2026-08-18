#!/usr/bin/env bash
set -o errexit

python -m pip install -r requirements.txt
python manage.py check --deploy
python manage.py collectstatic --no-input
python manage.py migrate --noinput
