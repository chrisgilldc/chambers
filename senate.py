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
        Update the Senate. Load if necessary.

        :return:
        """
        if force:
            # Always load if we're forced, or if we don't have any data yet.
            self._logger.info("Force load requested.")
            self._load()
            return True
        elif datetime.now(timezone.utc) > self.next_update:
            self._load()
            return True
        else:
            return False
        #     since_update = ( datetime.now(self._dctz) - self._updated ).seconds
        #     self._logger.debug(f"Time since last update {since_update}s")
        #     if not self.convened:
        #         if self.convenes_at is not None:
        #             # If we're within 10 minutes of the convening time, update once a minute.
        #             if (self.convenes_at - timedelta(minutes=10) ) < datetime.now(timezone.utc) and since_update > 60:
        #                 self._load()
        #                 return True
        #         else:
        #             if since_update > 600:
        #                 self._load()
        #                 return True
        #     else:
        #         if since_update > 120:
        #             self._load()
        #             return True
        # return False

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

        if convene_dt < datetime.now(self._dctz):
            convened = True
            self._convened_at = datetime.now(self._dctz)
            self._convenes_at = None
            self._adjourned_at = None
        elif convene_dt > datetime.now(self._dctz):
            convened = False
            self._convenes_at = convene_dt
            self._convened_at = None
        else:
            raise ValueError("Convened is in an impossible state.")

        # Track when we adjourn, since the JSON doesn't provide this.
        if not convened and self._convened:
            self._adjourned_at = datetime.now(self._dctz)

        self._updated = datetime.now(self._dctz).replace(microsecond=0)
        self._convened = convened