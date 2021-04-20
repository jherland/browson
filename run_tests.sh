#!/bin/sh

set -e -x

PYTHONPATH=$(pwd) pytest . "$@"
black browson/ tests/ -l79
flake8
