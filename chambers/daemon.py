"""
Python Daemon to watch Congressional chambers and publish status via MQTT.
"""

import logging
import json
import os
import signal
import sys
import paho.mqtt.client
import chambers
from datetime import datetime

class ChamberWatcher:
    """
    Class to monitor the US Congress. Create one, then run it.
    """

    def __init__(self, mqtt_host, mqtt_username, mqtt_password, mqtt_port=1883, mqtt_qos=0,
                 mqtt_client_id = 'chambers', mqtt_base = 'chambers', ha_base = 'homeassistant', log_level=logging.INFO):
        """

        :param mqtt_host: MQTT host to connect to.
        :type mqtt_host: str
        :param mqtt_username: MQTT username to use.
        :type mqtt_username: str
        :param mqtt_password: MQTT password to use.
        :type mqtt_password: str
        :param mqtt_port: MQTT port. Defaults to '1883'.
        :type mqtt_port: int
        :param mqtt_qos: Quality of Service to use. Defaults to 0.
        :type mqtt_qos: int
        :param mqtt_client_id: ID to use when connecting to the broker. Defaults to 'chambers'
        :type mqtt_client_id: str
        :param mqtt_base: Base of the MQTT topics. Defaults to 'chambers'. Probably keep this the same.
        :type mqtt_base: str
        :param ha_base: Base of the Home Assistant topics. Default is 'homeassistant'. Don't update unless you've changed it.
        :type ha_base: str
        :param log_level: Level to log at. Defaults to 'warning'.
        :type log_level: str
        """

        # Set up the logger!
        self._logger = logging.getLogger('Chambers')
        self._logger.setLevel(log_level)
        # Create the console stream handler.
        ch = logging.StreamHandler()
        # Set format.
        ch.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        # Set logging level.
        ch.setLevel(logging.DEBUG)
        self._logger.addHandler(ch)

        self._logger.info("Chambers Initializing...")
        # Save parameters
        self._client_id = mqtt_client_id
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._mqtt_username = mqtt_username
        self._mqtt_password = mqtt_password
        self._mqtt_qos = mqtt_qos
        self._mqtt_base = mqtt_base
        self._ha_base = ha_base

        # Make default variables.
        self._mqtt_status = 'disconnected'

        # Make the client.
        self._create_mqtt_client()

        # Connect!
        self.connect()

        # Make the chamber objects.
        self._house = chambers.House(parent_logger=self._logger)
        self._senate = chambers.Senate(parent_logger=self._logger)

    def _create_mqtt_client(self):
        """
        Create the MQTT client object, connect appropriate callbacks.

        :return:
        """

        # Make the client object.
        self._mqtt_client = paho.mqtt.client.Client(
            paho.mqtt.client.CallbackAPIVersion.VERSION2,
            client_id=self._client_id
        )
        # Set the username and password
        self._mqtt_client.username_pw_set(
            username=self._mqtt_username,
            password=self._mqtt_password
        )
        # Set last will
        self._mqtt_client.will_set(self._topics["running"], payload="false", qos=self._mqtt_qos, retain=True)
        # Connect callbacks.
        self._mqtt_client.on_connect = self._on_connect
        self._mqtt_client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Connection callback.

        :param client: Calling client object.
        :param userdata:
        :param flags:
        :param rc:
        :param properties:
        :return:
        """
        self._logger.info("Connected to MQTT Broker with result code: {}".format(rc))
        # Set connection status to connected.
        self._mqtt_status = "connected"
        # Send the online message.
        self._send_online()
        # Subscribe to the Home Assistant status topic.
        self._mqtt_client.subscribe(f"homeassistant/status")
        # Attach the general message callback
        # self._mqtt_client.on_message = self._on_message
        # Run Home Assistant Discovery
        self._ha_discovery()

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """
        Disconnection callback.

        :param client: The client instance for this callback.
        :param userdata: Private user data as set, if any.
        :param rc: Disconnect reason code as received from the broker.
        :return:
        """
        if rc != 0:
            self._logger.warning("Unexpected disconnect with reason - '{}'".format(rc.getName()))
            self._mqtt_status = "disconnected"
        else:
            self._mqtt_status = "disconnected-planned"
            # Send an HA Offline message. The will should handle this too, but let's be clean.
            self._send_offline()
        # self._reconnect_timer = time.monotonic()
        self._mqtt_client.loop_stop()

    def _pub_message(self, topic, payload, send_json=False):
        """
        Publish a message

        :param topic: Topic to publish the message to.
        :param payload: The payload to publish.
        # :param repeat: Repeat this even if the same payload has already been published.
        :param send_json: Convert to JSON before publication.
        :param send_json: bool
        :return:
        """

        # Convert to JSON if requested.
        if send_json:
            outbound_message = json.dumps(payload)
        else:
            outbound_message = payload

        if isinstance(payload, datetime):
            outbound_message = payload.isoformat()

        # Publish it!
        self._mqtt_client.publish(topic, outbound_message)

    @property
    def _topics(self):
        """
        Topics dictionary property. Only accses this after initialization since these defintions are context-dependent.

        :return: Dictionary of full topic targets.
        :rtype: dict
        """
        return {
            "running": f"{self._mqtt_base}/running",
            "house_convened": f"{self._mqtt_base}/house/convened",
            "house_next_update": f"{self._mqtt_base}/house/next_update",
            "house_adjourned_at": f"{self._mqtt_base}/house/adjourned_at",
            "house_convened_at": f"{self._mqtt_base}/house/convened_at",
            "house_convenes_at": f"{self._mqtt_base}/house/convenes_at",
            "senate_convened": f"{self._mqtt_base}/senate/convened",
            "senate_next_update": f"{self._mqtt_base}/senate/next_update",
            "senate_adjourned_at": f"{self._mqtt_base}/senate/adjourned_at",
            "senate_convened_at": f"{self._mqtt_base}/senate/convened_at",
            "senate_convenes_at": f"{self._mqtt_base}/senate/convenes_at"
        }

    def run(self):
        """
        Main run loop.
        """
        self._logger.debug("Entering run loop.")
        while True:
            if self._mqtt_status == 'disconnected':
                self.connect()
            elif self._mqtt_status in ('connecting','disconnected-planned'):
                pass
            else:
                # Update the House.
                if self._house.update():
                    self._pub_message(self._topics['house_convened'], self._house.convened)
                    self._pub_message(self._topics['house_adjourned_at'], self._house.adjourned_at)
                    self._pub_message(self._topics['house_convened_at'], self._house.convened_at)
                    self._pub_message(self._topics['house_convenes_at'], self._house.convenes_at)
                    self._logger.info("House next update: {} ({})".format(self._house.next_update, type(self._house.next_update)))
                    self._pub_message(self._topics['house_next_update'], self._house.next_update)
                # Update the Senate.
                if self._senate.update():
                    self._pub_message(self._topics['senate_convened'], self._senate.convened)
                    self._pub_message(self._topics['senate_adjourned_at'], self._senate.adjourned_at)
                    self._pub_message(self._topics['senate_convened_at'], self._senate.convened_at)
                    self._pub_message(self._topics['senate_convenes_at'], self._senate.convenes_at)
                    self._logger.info("Senate next update: {} ({})".format(self._senate.next_update, type(self._senate.next_update)))
                    self._pub_message(self._topics['senate_next_update'], self._senate.next_update)

    @property
    def __class__(self):
        return super().__class__

    # System Signal Handling
    def _register_signal_handlers(self):
        """
        Sets up POSIX signal handlers.
        :return:
        """
        self._logger.debug("Registering signal handlers.")
        # Reload configuration.
        signal.signal(signal.SIGHUP, self._signal_handler)
        # Terminate cleanly.
        # Default quit
        signal.signal(signal.SIGTERM, self._signal_handler)
        # Quit and dump core. Not going to do that, so
        signal.signal(signal.SIGQUIT, self._signal_handler)

        # All other signals are some form of error.
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGILL, self._signal_handler)
        signal.signal(signal.SIGTRAP, self._signal_handler)
        signal.signal(signal.SIGABRT, self._signal_handler)
        signal.signal(signal.SIGBUS, self._signal_handler)
        signal.signal(signal.SIGFPE, self._signal_handler)
        # signal.signal(signal.SIGKILL, receiveSignal)
        signal.signal(signal.SIGUSR1, self._signal_handler)
        signal.signal(signal.SIGSEGV, self._signal_handler)
        signal.signal(signal.SIGUSR2, self._signal_handler)
        signal.signal(signal.SIGPIPE, self._signal_handler)
        signal.signal(signal.SIGALRM, self._signal_handler)

    def cleanup_and_exit(self, signalNumber=None, message=None):
        """
        Shut off controls and displays, then exit.

        :param signalNumber: Signal called for exit.
        :param message: Message for exit
        :return: None
        """
        if isinstance(signalNumber, int) and 'signal' in sys.modules:
            signame = signal.Signals(signalNumber).name
            self._logger.critical("Exit triggered by {}. Performing cleanup actions.".format(signame))
        else:
            self._logger.critical("Exit requested. Performing cleanup actions.")

        # All we should need to do to cleanup is send an offline message to HA. We could rely on the will, but this is
        # maybe more "proper"?
        self._send_offline()

        self._logger.critical("Cleanup complete.")
        # Return a signal. We consider some exits clean, others we throw back the signal number that called us.
        if signalNumber in (None, 15):
            sys.exit(0)
        else:
            sys.exit(signalNumber)

    def connect(self):
        """
        Connect to the broker.

        :return:
        """
        self._logger.info(f"Connecting to broker {self._mqtt_host}:{self._mqtt_port}")
        try:
            self._mqtt_client.connect(self._mqtt_host, self._mqtt_port)
            self._mqtt_client.loop_start()
            self._mqtt_status = 'connecting' # This is connect*ing* because we need to await the ACK from the broker.
        except ConnectionError as error:
            self._logger.error(f"Could not connect to MQTT broker: {error}")
            sys.exit(1)
        else:
            self._logger.info("Connection started. Awaiting broker acknowledgement.")

    def _send_online(self):
        """
        Publish an online message.
        :return:
        """
        self._mqtt_client.publish(self._topics['running'], payload="true", retain=True)

    def _send_offline(self):
        """
        Publish an offline message.
        :return:
        """
        self._mqtt_client.publish(self._topics['running'], payload="false", retain=True)

    def _signal_handler(self, signalNumber=None, frame=None):
        """

        :param signalNumber: Signal number
        :param frame: Frame
        :return:
        """
        print("Caught signal {}".format(signalNumber))
        self.cleanup_and_exit(signalNumber)

    def _ha_discovery(self):
        """
        Run Home Assistant Discovery

        :return:
        """

        discovery_dict = {
            'name': "Running",
            'object_id': "chambers_running",
            'device': self._ha_device_info(),
            'device_class': 'running',
            'unique_id': f"{self._client_id}_running",
            'state_topic': self._topics['running'],
            'icon': 'mdi:play',
            'payload_on': 'true',
            'payload_off': 'false'
        }
        discovery_topic = f"{self._ha_base}/binary_sensor/{self._client_id}/running/config"
        self._pub_message(discovery_topic, discovery_dict, send_json=True)
        # self._mqtt_client.publish(discovery_topic, discovery_json, True)
        # self._topics_outbound['connectivity']['discovery_time'] = time.monotonic()

        for chamber in ('house', 'senate'):
            convened_dict = {
                'name': f"{chamber.capitalize()} Convened",
                'object_id': f"chambers_{chamber}_convened",
                'device': self._ha_device_info(),
                'unique_id': f"{self._client_id}_{chamber}_convened",
                'state_topic': self._topics[f"{chamber}_convened"],
                'payload_on': 'True',
                'payload_off': 'False',
                'availability': self._ha_availability()
            }

            self._pub_message(
                f"{self._ha_base}/binary_sensor/{self._client_id}/{chamber}_convened/config",
                convened_dict, send_json=True)

            adjourned_at_dict = {
                'name': f"{chamber.capitalize()} Adjourned At",
                'object_id': f"{chamber}_adjourned_at",
                'device': self._ha_device_info(),
                'unique_id': f"{self._client_id}_{chamber}_adjourned_at",
                'state_topic': self._topics[f"{chamber}_adjourned_at"],
                'device_class': 'timestamp',
                'availability': self._ha_availability()
            }

            self._pub_message(
                f"{self._ha_base}/sensor/{self._client_id}/{chamber}_adjourned_at/config",
                adjourned_at_dict, send_json=True)

            convened_at_dict = {
                'name': f"{chamber.capitalize()} Convened At",
                'object_id': f"{chamber}_convened_at",
                'device': self._ha_device_info(),
                'unique_id': f"{self._client_id}_{chamber}_convened_at",
                'state_topic': self._topics[f"{chamber}_convened_at"],
                'device_class': 'timestamp',
                'availability': self._ha_availability()
            }

            self._pub_message(
                f"{self._ha_base}/sensor/{self._client_id}/{chamber}_convened_at/config",
                convened_at_dict, send_json=True)

            convenes_at_dict = {
                'name': f"{chamber.capitalize()} Convenes At",
                'object_id': f"{chamber}_convenes_at",
                'device': self._ha_device_info(),
                'unique_id': f"{self._client_id}_{chamber}_convenes_at",
                'state_topic': self._topics[f"{chamber}_convenes_at"],
                'device_class': 'timestamp',
                'availability': self._ha_availability()
            }

            self._pub_message(
                f"{self._ha_base}/sensor/{self._client_id}/{chamber}_convenes_at/config",
                convenes_at_dict, send_json=True)

    def _ha_availability(self):
        """
        Availability settings for HA entities.

        :return: dict
        """
        return_data = dict(
            topic=self._topics['running'],
            payload_not_available="false",
            payload_available="true"
        )
        return return_data

    def _ha_device_info(self):
        """
        Device information to include in Home Assistant discovery messages.
        """
        return_data = dict(
            name="Chambers",
            identifiers=[self._client_id],
            manufacturer='ConHugeCo',
            model='Chambers',
            sw_version=str(chambers.__version__)
        )
        return return_data

def chambers_cli():

    # If run as main, try to get everything from the environmemnt and run.

    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_PORT = os.getenv("MQTT_PORT") or 1883
    MQTT_USERNAME = os.getenv("MQTT_USERNAME") or 'chambers'
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
    MQTT_BASE = os.getenv("MQTT_BASE") or 'chambers'
    MQTT_HABASE = os.getenv("MQTT_HABASE") or 'homeassistant'
    MQTT_CLIENTID = os.getenv("MQTT_CLIENTID") or 'chambers'
    MQTT_QOS = os.getenv("MQTT_QOS") or 0
    LOGLEVEL = os.getenv("LOGLEVEL") or 'INFO'

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

    cw = ChamberWatcher(
        mqtt_host=MQTT_HOST,
        mqtt_port=MQTT_PORT,
        mqtt_username=MQTT_USERNAME,
        mqtt_password=MQTT_PASSWORD,
        mqtt_qos=MQTT_QOS,
        mqtt_client_id=MQTT_CLIENTID,
        mqtt_base=MQTT_BASE,
        ha_base = MQTT_HABASE,
        log_level=LOGVAL
    )
    cw.run()

if __name__ == "__main__":
    sys.exit(chambers_cli())