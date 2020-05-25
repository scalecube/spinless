#!/usr/bin/env bash

cd "$TF_STATE" && /usr/local/bin/terraform init "$APP_WORKING_DIR/$TF_WORKING_DIR"
cd "$APP_WORKING_DIR" && python ./api.py
