#!/usr/bin/env bash
ENV=Dev-V3 python3 manage.py createinitialrevisions
ENV=Dev-V3 python3 manage.py invalidate_cachalot
ENV=Dev-V3 python3 manage.py clear_cache
ENV=Dev-V3 python3 manage.py clean_pyc
