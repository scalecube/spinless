#!/usr/bin/env bash

/usr/local/bin/helm init --client-only --tiller-namespace=tiller
cd "$TF_STATE" && /usr/local/bin/terraform init "$TF_WORKING_DIR"
cd "$APP_WORKING_DIR" && python ./start_app.py
