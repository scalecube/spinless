#!/usr/bin/env bash

sed -i "s/tf_token/$TF_VAR_token/g" "$TF_CLI_CONFIG_FILE"
sed -i "s/ORG/$ORG/g" "$TF_BACKEND_CONFIG_FILE"
cd "$TF_STATE" && /usr/local/bin/terraform init "$APP_WORKING_DIR/$TF_WORKING_DIR"
cd "$APP_WORKING_DIR" && python ./api.py
