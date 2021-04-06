#!/bin/sh

set -e -x

pytest . "$@"
black browson.py node.py style.py test_browson.py test_node.py -l79
flake8 browson.py node.py style.py test_browson.py test_node.py
