#!/bin/sh

/usr/local/bin/helm init --client-only --tiller-namespace=tiller
python ./start_app.py