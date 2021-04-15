#!/bin/sh

set -e -x

pytest . "$@"
black browson.py node.py nodeview.py style.py utils.py test_browson.py test_node.py test_style.py test_utils.py -l79
flake8
