#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
playwright install
playwright install-deps
