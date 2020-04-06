#!/bin/sh

/usr/local/bin/helm init --client-only --tiller-namespace=tiller
/usr/local/bin/terraform init "$TF_WORKING_DIR"
python ./start_app.py