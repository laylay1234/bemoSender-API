#!/bin/bash
python3 manage.py compilemessages -i venv -i public -i requirements.txt -i requirements.txt.py
python3 manage.py makemessages --no-wrap --no-location --no-obsolete -i venv -i public -i requirements.txt -i requirements.txt.py -a --domain djangojs
python3 manage.py makemessages --no-wrap --no-location --no-obsolete -i venv -i public -i requirements.txt -i requirements.txt.py -a
