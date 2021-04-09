#!/bin/sh

set -e -x

pytest . "$@"
black browson.py node.py style.py test_browson.py test_node.py test_style.py -l79
flake8
