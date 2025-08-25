#!/usr/bin/with-contenv bashio
# Chambers Home Assistant Add-On Shell script

# Set MQTT environment variables.
export MQTT_HOST=$(bashio::services mqtt "host")
export MQTT_PORT=$(bashio::services mqtt "port")
export MQTT_USERNAME=$(bashio::services mqtt "username")
export MQTT_PASSWORD=$(bashio::services mqtt "password")
export LOGLEVEL=$(bashio::config "log_level")

# Run chambers.
chambers