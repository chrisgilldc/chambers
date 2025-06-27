"""
Senate current status and calendar
"""

from .chamber import Chamber
import chambers.const
from datetime import datetime, timezone, timedelta
import json
import logging
import re
import requests
import urllib.request
import xml.etree.ElementTree as ET
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

        # Try to load today. Will 404 if House isn't in session yet.
        # try:
        #     today_response = requests.get(House.URL_BASE + datetime.now().strftime('%Y%m%d') + ".xml")
        # except requests.exceptions.ConnectionError as ce:
        #     self._logger.error(f"Exception while trying to retrieve today's journal - '{ce}'")
        #     return False
        # else:
        #     if today_response.ok:
        #         self._logger.info("Loading today's House floor proceedings.")
        #         # Response is okay, process it.
        #         event_count = self._load_xml(today_response.content)
        #         self._logger.info(f"Today's proceedings resulted in {event_count} events.")

        # Load most recent day's activity.
        i = 1
        found_response = False
        while not found_response:
            search_date = (datetime.now() - timedelta(days=i))
            fa_url = self._floor_activity_url(search_date.month, search_date.day, search_date.year)
            self._logger.info(f"Trying to load from Floor Activity URL {fa_url}")
            old_response = requests.get(fa_url)
            if old_response.ok:
                self._logger.info("Found floor proceedings for {}. Loading.".format(
                    (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')
                ))
                # pprint(old_response.content)
                # if today_response.ok:
                #     self._logger.info("Loading to extract adjournment.")
                #     # Load the previous legislative days' XML only to get the adjournment data.
                #     event_count = self._load_xml(old_response.content)
                #     if event_count != 1:
                #         self._logger.error("Could not load adjournment from journal on {}".format(
                #             (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')))
                #     else:
                #         self._logger.info("Loaded adjournment from journal.")
                # else:
                event_count = self._load_xml(old_response.content)
                self._logger.info("Loaded {} events from journal on {}".format(event_count,(datetime.now()
                        - timedelta(days=i)).strftime('%d %b %Y') ))
                found_response = True
            i += 1
        self._logger.info("Sorting events.")
        # self._sort_events()
        # self._trim_event_log()
        self._updated = datetime.now(self._dctz)
        self._logger.info("Load complete.")
        return True

    def _load_xml(self, floor_proceedings):
        """
        Load a Senate Floor Proceedings XML.

        :return:
        """
        # Create an XML tree.
        senate_tree = ET.fromstring(floor_proceedings)
        # Pull out the base date. This has to get combined with the time later.
        base_date = datetime.strptime(senate_tree.find('date_iso_8601').text, '%Y-%m-%d')
        # Is the Senate in Recess or Adjourned? Check for a section with the recess tag.
        recess = senate_tree.find("section[@type='recess']/content")
        if isinstance(recess,ET.Element):
            recess_text = recess.text.replace("\n", "")
            # Pull out the adjournment information.
            aa_string = re.search("at(?:\\s*)(\\d{1,2}:\\d{1,2}) (p|a)", recess_text)
            ampm_indicator = 'pm' if aa_string.group(2) == 'p' else 'am'
            aa_string = aa_string.group(1) + " " + ampm_indicator
            adjourned_at = datetime.combine(base_date, datetime.strptime(aa_string, "%I:%M %p").time())

            # Make an event out of this.
            adjourned_event = {
                'timestamp': adjourned_at,
                'type': chambers.const.ADJOURN,
                'description': recess_text
            }
            # Add the adjournment event to the event log.
            self._add_floor_action(adjourned_event)

            # Find the next convening.
            until_pos = re.search("until", recess_text)
            convening_text = recess_text[until_pos.span()[0]:]
            ct_string = re.search("until(?:\\s*)(\\d{1,2}:\\d{1,2}) (p|a)", convening_text)
            ampm_indicator = 'pm' if ct_string.group(2) == 'p' else 'am'
            ct_string = ct_string.group(1) + " " + ampm_indicator
            convene_time = datetime.strptime(ct_string, "%I:%M %p").time()
            # Does this reference tomorrow?
            if "tomorrow" in convening_text:
                convenes_at = datetime.combine((base_date + timedelta(days=1)).date(), convene_time)
                convenes_event = {
                    'timestamp': convenes_at,
                    'type': chambers.const.CONVENE_SCHEDULED,
                    'description': recess_text
                }
                self._add_floor_action(convenes_event)
            return 2
        elif recess is None:
            return 0

    def _add_floor_action(self, floor_action):
        """
        Add an action to the event log.
        This is like the House version, but only considers convenings and adjournment.

        :return: True if added, false if not.
        :rtype: bool
        """
        do_add = False
        del_list = []
        # Decide if this action *should* be added. Prevents duplicates.
        if len(self._events) == 0:
            do_add = True
        else:
            i = 0
            while i < len(self._events):
                if self._events[i]['timestamp'] == floor_action['timestamp']:
                    self._logger.debug("Floor action already exists at timestamp {}. Will replace.".format(floor_action['timestamp']))
                    del_list.append(i)
                    do_add = True
                    break
                else:
                    do_add = True
                i += 1

        if do_add:
            self._events.append(floor_action)

        # Reverse the list.
        del_list.reverse()
        for item in del_list:
            self._events.pop(item)
        return True

    @staticmethod
    def _floor_activity_url(month, day, year):
        """ Build a floor activity URL for a particular date.

        :param month: The month
        :type month: int
        :param day: The day
        :type day: int
        :param year: The year, four digits.
        :type year: int
        :returns: The full URL to use.
        :rtype: str
        """

        return f"https://www.senate.gov/legislative/LIS/floor_activity/{month:02}_{day:02}_{year}_Senate_Floor.xml"