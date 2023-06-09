#!/bin/bash
python3 manage.py graph_models bemosenderrr --pygraphviz --output model.png
python3 manage.py generateschema > model.openapi
