from chambers.daemon import ChamberWatcher
import logging
import pathlib
import sys

MQTT_HOST = '172.18.47.10'
MQTT_PORT = 1883
MQTT_USERNAME = 'chambers_test'
MQTT_PASSWORD = 'test1234'
MQTT_BASE = 'chambers_test'
MQTT_HABASE = 'homeassistant'
MQTT_CLIENTID = 'chambers_test'
MQTT_QOS = 0
LOGLEVEL = 'DEBUG'
LOGMQTT = False
CLEAR_CACHE = False

LOGVAL = logging.getLevelName(LOGLEVEL.upper())
if not isinstance(LOGVAL, int):
    print(f"Requested logging level {LOGLEVEL} is not valid. Defaulting to 'WARNING'")
    LOGVAL = logging.getLevelName('INFO')

try:
    MQTT_PORT = int(MQTT_PORT)
except ValueError:
    print(f"MQTT_PORT must be an integer number!")
    sys.exit(1)

print(f"Using Environment values:\nHOST: {MQTT_HOST}\nPORT: {MQTT_PORT}\nUSERNAME: {MQTT_USERNAME}\n"
      f"PASSWORD: {MQTT_PASSWORD}\nQOS: {MQTT_QOS}\nClient ID: {MQTT_CLIENTID}\nBase: {MQTT_BASE}\n"
      f"HA Base: {MQTT_HABASE}\nLog Level: {LOGLEVEL} ({LOGVAL})")

if CLEAR_CACHE:
    print("Clearing cache as requested!")
    for cache_file in pathlib.Path('.').rglob('*.cache'):
        print(f"Removing cache file {cache_file}")
        pathlib.Path.unlink(cache_file)

cw = ChamberWatcher(
    mqtt_host=MQTT_HOST,
    mqtt_port=MQTT_PORT,
    mqtt_username=MQTT_USERNAME,
    mqtt_password=MQTT_PASSWORD,
    mqtt_qos=MQTT_QOS,
    mqtt_client_id=MQTT_CLIENTID,
    mqtt_base=MQTT_BASE,
    ha_base=MQTT_HABASE,
    log_level=LOGVAL,
    log_mqtt=LOGMQTT
)
cw.run()