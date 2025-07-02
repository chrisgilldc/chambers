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

from .exceptions import ChamberExceptionRecoverable


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

    # @property
    # def adjourned_at(self):
    #     """
    #     When the chamber adjourned. Returns datetime if adjourned, None if in session.
    #
    #     :return: datetime or None
    #     """
    #
    #     return self._adjourned_at

    # @property
    # def convened(self):
    #     """
    #     Is the Senate convened?
    #     :return:
    #     """
    #     return self._convened
    #
    #
    # @property
    # def convened_at(self):
    #     """
    #     When the Senate convened for its main session. Does *not* consider Recesses. Will return Datetime if convened,
    #     None if adjourned.
    #
    #     :return: datetime or None
    #     """
    #
    #     return self._convened_at
    #
    # @property
    # def convenes_at(self):
    #     """
    #     When the Senate will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.
    #
    #     :return: datetime or None
    #     """
    #
    #     return self._convenes_at

    def update(self, force=False):
        """
        Update the Senate. Load if necessary.

        :return:
        """
        if force:
            # Always load if we're forced, or if we don't have any data yet.
            self._logger.info("Force load requested.")
            try:
                self._load()
            except urllib.error.URLError as urle:
                self._logger.error("Cannot connect to Senate site ({}")
                raise ChamberExceptionRecoverable from urle
            return True
        elif datetime.now(timezone.utc) > self.next_update:
            self._load()
            return True
        else:
            return False


    def _load(self, xml=True, json=True):
        """
        Load data about the state of the Senate from XML and JSON sources.
        :return:
        """

        # Load the JSON.
        if json:
            loaded = self._load_json()
            self._logger.info(f"Loaded {loaded} events from JSON.")

        # Try the XML. XML usually isn't published until the day after, so this is only useful for the previous day's
        # adjournment. Still, try today, maybe that will change.
        # This will start with today's date and try each successive previous day until two days worth of data are loaded.
        if xml:
            i = 0
            days_loaded = 0
            while days_loaded < 3:
                search_date = (datetime.now() - timedelta(days=i))
                fa_url = self._floor_activity_url(search_date.month, search_date.day, search_date.year)
                self._logger.info(f"Trying to load from Floor Activity URL {fa_url}")
                senate_xml_response = requests.get(fa_url)
                # When a day's XML doesn't exist, the Senate returns a 404 page via 302 redirect. This reads as 'okay' but
                # isn't parseable (obviously). Try to filter this via by checking for two known good states.
                loadable = False
                if len(senate_xml_response.history) == 0 and senate_xml_response.ok:
                    self._logger.debug("Only one response and is okay. Will load XML.")
                    # OK status and *no* history. This is okay to load.
                    loadable = True
                elif senate_xml_response.history[0].status_code == 200:
                    self._logger.debug("Load history exists. First load is 200. Will load XML.")
                    # There *is* a history, and the first status code is a 200. This is loadable.
                    loadable = True
                else:
                    self._logger.debug("No good response history, will not load, probably not XML.")
                if loadable:
                    self._logger.info("Found floor proceedings for {}. Loading.".format(
                        (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')
                    ))
                    event_count = self._load_xml(senate_xml_response.content, fa_url)
                    self._logger.info("Loaded {} events from journal on {}".format(event_count,(datetime.now()
                            - timedelta(days=i)).strftime('%d %b %Y') ))
                    days_loaded += 1
                i += 1


        self._logger.info("Sorting events.")
        self._sort_events()
        # self._trim_event_log()
        self._updated = datetime.now(self._dctz)
        self._logger.info("Load complete.")
        return True

    def _load_json(self):
        """
        Load the Senate's Floor Activity JSON as an event.
        :return:
        """

        try:
            with urllib.request.urlopen(Senate.floor_schedule_url) as url:
                senate_data = json.load(url)
        except urllib.error.URLError as urle:
            raise ChamberExceptionRecoverable from urle

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
            event_type = chambers.const.CONVENE
        elif convene_dt > datetime.now(self._dctz):
            convened = False
            event_type = chambers.const.CONVENE_SCHEDULED,
        else:
            raise ValueError("Convened is in an impossible state.")

        json_event = {
            'timestamp': convene_dt,
            'type': event_type,
            'description': "Event from Floor Activity JSON",
            'source': 'JSON',
            'source_url': Senate.floor_schedule_url
        }

        # Add the event if the JSON state isn't consistent with the current state in the object.
        if convened != self._convened:
            self._add_floor_action(json_event)
            return 1
        return 0


    def _load_xml(self, floor_proceedings, source_url):
        """
        Load a Senate Floor Proceedings XML.

        :return:
        """
        # List of new events to add to the main event log.
        new_events = []

        # Create an XML tree.
        senate_tree = ET.fromstring(floor_proceedings)
        # Pull out the base date. This has to get combined with the time later.
        base_date = datetime.strptime(senate_tree.find('date_iso_8601').text, '%Y-%m-%d')
        self._logger.debug(f"Extracted base date {base_date}")

        # Parse the Intro Text for a convening *time*
        # Search and pull out the text. This has information about convening.
        try:
            intro_text = senate_tree.find("intro_text").text
        except AttributeError:
            self._logger.info("File has no 'intro_text', nothing usable here.")
            return 0

        # Replace any embedded CRs. This makes the regular expression easier.
        intro_text = intro_text.replace('\n','')
        self._logger.debug("Intro text found: {}".format(intro_text))
        convene_time_search = re.search("to order at\\s*(\\d{1,2}:?\\d{0,2}) ([a|p]\\.?m\\.?)", intro_text)

        if len(convene_time_search.groups()) == 2:
            # Make the timestamp.
            ampm = convene_time_search.group(2).replace('.','')
            if ':' not in convene_time_search.group(1):
                convene_dt = datetime.strptime(f"{convene_time_search.group(1)}:00 {ampm}", "%I:%M %p")
            else:
                convene_dt = datetime.strptime(f"{convene_time_search.group(1)} {ampm}", "%I:%M %p")
            convene_dt = datetime.combine(base_date.date(), convene_dt.time()).replace(tzinfo=self._dctz)
            # Make a convene event
            convene_event = {
                'timestamp': convene_dt,
                'type': chambers.const.CONVENE,
                'description': intro_text,
                'source': 'XML',
                'source_url': source_url
            }
            self._logger.debug("Added Convene event {}".format(convene_event))
            new_events.append(convene_event)
        else:
            self._logger.debug("Could not extract sufficient data from intro text for convene event.")

        # Check for a 'recess' or 'adjournment' at the end of the activity.
        recess = senate_tree.find("section[@type='recess']/content")
        depart_type = None
        if recess is not None:
            depart_type = chambers.const.RECESS_TIME
            depart_string = recess
        else:
            adjournment = senate_tree.find("section[@type='adjournment']/content")
            if isinstance(adjournment, ET.Element):
                depart_type = chambers.const.ADJOURN
                depart_string = adjournment
            else:
                depart_type = None

        if depart_type is not None:
            depart_string = depart_string.text.replace("\n", "")
            self._logger.debug("Depart text is: {}".format(depart_string))
            # Pull out the adjournment information.
            aa_string = re.search("at\\s*(\\d{1,2}:\\d{1,2}) ([a|p]\\.?m\\.?)", depart_string)
            self._logger.debug("Extracted data for departure - Time '{}', am/pm '{}'".format(aa_string.group(1), aa_string.group(2)))
            ampm = aa_string.group(2).replace('.','')
            aa_string = aa_string.group(1) + " " + ampm
            depart_at = datetime.combine(base_date, datetime.strptime(aa_string, "%I:%M %p").time()).replace(
                tzinfo=self._dctz)

            # Make an event out of this.
            depart_event = {
                'timestamp': depart_at,
                'type': depart_type,
                'description': depart_string,
                'source': 'XML',
                'source_url': source_url
            }
            new_events.append(depart_event)

            # Find the next convening.
            until_pos = re.search("until", depart_string)
            convening_text = depart_string[until_pos.span()[0]:]
            self._logger.debug(f"Convene text is: {convening_text}")
            #ct_string = re.search("until(?:\\s*)(\\d{1,2}:?\\d{0,2}) ([a|p].?m.?)", convening_text)
            ct_string = re.search("until\\s*(\\d{1,2}:?\\d{0,2}) ([a|p]\\.?m\\.?)", convening_text)
            if ct_string is None:
                if 'noon' in convening_text:
                    ct_string = "12:00 pm"
            else:
                ampm = ct_string.group(2).replace('.','')
                if ":" in ct_string.group(1):
                    ct_string = ct_string.group(1) + " " + ampm
                else:
                    ct_string = ct_string.group(1) + ":00 " + ampm
            convene_time = datetime.strptime(ct_string, "%I:%M %p").time().replace(tzinfo=self._dctz)
            # Does this reference tomorrow?
            if "tomorrow" in convening_text:
                convenes_at = datetime.combine((base_date + timedelta(days=1)).date(), convene_time)
                convenes_event = {
                    'timestamp': convenes_at,
                    'type': chambers.const.CONVENE_SCHEDULED,
                    'description': depart_string,
                    'source': 'XML',
                    'source_url': source_url
                }
                new_events.append(convenes_event)

        added_events = 0
        for event in new_events:
            self._add_floor_action(event)
            added_events += 1
        return added_events

    def _add_floor_action(self, floor_action):
        """
        Add an action to the event log.
        This is like the House version, but only considers convenings and adjournment.

        :return: True if added, false if not.
        :rtype: bool
        """
        # Assume we'll add.
        do_add = True
        del_list = []
        # Decide if this action *should* be added. Prevents duplicates.
        # if len(self._events) == 0:
        #     do_add = True
        # else:
        i = 0
        while i < len(self._events):
            if self._events[i]['timestamp'] == floor_action['timestamp']:
                if self._events[i]['type'] == chambers.const.CONVENE and floor_action['type'] == chambers.const.CONVENE_SCHEDULED:
                    self._logger.debug("Floor action already exists at timestamp {}. Existing action is an actual "
                                       "convene, new action is a scheduled convene. Will not replace.".
                                       format(floor_action['timestamp']))
                    # Since we don't want to have two convenes, block it here.
                    do_add = False
                else:
                    self._logger.debug("Floor action already exists at timestamp {}. Will replace.".
                                       format(floor_action['timestamp']))
                    del_list.append(i)
                    # do_add = True
                break
            i += 1

        if do_add:
            self._events.append(floor_action)

        # Reverse the list.
        self._logger.debug("Items to delete: {}".format(del_list))
        del_list.reverse()
        for item in del_list:
            self._logger.debug("Removing item at position {}, timestamp {}".format(item, self._events[item]['timestamp']))
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