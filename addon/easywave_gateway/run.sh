#!/usr/bin/with-contenv bashio
set -e

export EASYWAVE_SERIAL_PORT="$(bashio::config 'serial_port')"
export EASYWAVE_BAUD="$(bashio::config 'baud')"
export EASYWAVE_TX_ENABLED="$(bashio::config 'tx_enabled')"
export EASYWAVE_UNKNOWN_LIMIT="$(bashio::config 'unknown_limit')"
export EASYWAVE_MQTT_HOST="$(bashio::services mqtt host)"
export EASYWAVE_MQTT_PORT="$(bashio::services mqtt port)"
export EASYWAVE_MQTT_USERNAME="$(bashio::services mqtt username)"
export EASYWAVE_MQTT_PASSWORD="$(bashio::services mqtt password)"

exec python3 /app/gateway.py
