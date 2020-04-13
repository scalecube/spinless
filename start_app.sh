#!/usr/bin/env bash

cd "$APP_WORKING_DIR/$TF_STATE" && /usr/local/bin/terraform init "$APP_WORKING_DIR/$TF_WORKING_DIR"
cd "$APP_WORKING_DIR" && python ./start_app.py
