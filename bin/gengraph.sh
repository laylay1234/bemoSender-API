#!/bin/bash
python3 manage.py graph_models bemoSenderr --pygraphviz --output model.png
python3 manage.py generateschema > model.openapi
