"""
Senate current status and calendar
"""

from .chamber import Chamber
from datetime import datetime, timezone, timedelta
import json
import logging
import urllib.request
import zoneinfo

class Senate(Chamber):
    """
    Senate current status and calendar
    """
    floor_schedule_url = "https://www.senate.gov/legislative/schedule/floor_schedule.json"

    def __init__(self, parent_logger=None, log_level=logging.WARNING):
        """
        Base chamber object.

        :param parent_logger: Parent logger, if any.
        :param log_level: Log level.
        """
        super().__init__("Senate", parent_logger, log_level)

        self._convene_dt = None # Stores the information from the floor activity JSON
        self._convened_at = None
        self._convenes_at = None
        self._will_convene_at = None
        self._adjourned_at = None

        self._load_timestamp = 0 # When we last loaded the file from the site.

        self.update()

    @property
    def adjourned_at(self):
        """
        When the chamber adjourned. Returns datetime if adjourned, None if in session.

        :return: datetime or None
        """

        return self._adjourned_at

    @property
    def convened(self):
        """
        Is the Senate convened?
        :return:
        """
        return self._convened


    @property
    def convened_at(self):
        """
        When the Senate convened for its main session. Does *not* consider Recesses. Will return Datetime if convened,
        None if adjourned.

        :return: datetime or None
        """

        return self._convened_at

    @property
    def convenes_at(self):
        """
        When the Senate will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.

        :return: datetime or None
        """

        return self._convenes_at

    def update(self, force=False):
        """
        Update any internal timers.

        :return:
        """
        self._convene_dt = self._load()
        self._load_timestamp = datetime.now(timezone.utc).timestamp()

        if self._convene_dt < datetime.now(self._dctz):
            convened = True
            self._convened_at = datetime.now(self._dctz)
            self._convenes_at = None
            self._adjourned_at = None
        elif self._convene_dt > datetime.now(self._dctz):
            convened = False
            self._convenes_at = self._convene_dt
            self._convened_at = None
        else:
            raise ValueError("Convened is in an impossible state.")

        # Track when we adjourn, since the JSON doesn't provide this.
        if not convened and self._convened:
            self._adjourned_at = datetime.now(self._dctz)

        self._convened = convened

    def _load(self):
        """
        Load the Convening information from the Senate's JSON.
        :return:
        """
        with urllib.request.urlopen(Senate.floor_schedule_url) as url:
            senate_data = json.load(url)

        convene_dt = datetime(
                int(senate_data['floorProceedings'][0]['conveneYear']),
                int(senate_data['floorProceedings'][0]['conveneMonth']),
                int(senate_data['floorProceedings'][0]['conveneDay']),
                int(senate_data['floorProceedings'][0]['conveneHour']),
                int(senate_data['floorProceedings'][0]['conveneMinutes']),
                tzinfo=zoneinfo.ZoneInfo('America/New_York')
        )
        return convene_dt