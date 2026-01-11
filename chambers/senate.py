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


    def __init__(self, load_cache=True, tz = 'America/New_York', parent_logger=None, log_level=logging.WARNING):
        """
        Senate chamber object

        :param load_cache: Should the cache be loaded on initialization? Defaults to True.
        :type load_cache: bool
        :param tz: Timezone to output dates and times in. Defaults to DC time.
        :type tz: str
        :param parent_logger: Parent logger, if any.
        :type: logging.Logger
        :param log_level: Log level. Defaults to Warning.
        """
        super().__init__("Senate", load_cache, tz, parent_logger, log_level)

    def update(self, force=False, days=None):
        """
        Update the Senate. Load if time is up or force is specified.

        :param force: Force an update, even if time isn't up.
        :type force: bool
        :return: True if update performed, False if not.
        :rtype: bool
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
        elif self.next_update is None:
            self._logger.info("Next update is not set. Probably need to update now! Loading.")
            self._load()
            self._set_next_update()
            return True
        elif datetime.now(timezone.utc) > self.next_update:
            self._load(days=days)
            self._set_next_update()
            return True
        else:
            return False

    def _load(self, xml=True, json=True, days=None):
        """
        Load data about the state of the Senate from XML and JSON sources.

        :param xml: Should the Senate's XML sources be loaded?
        :type xml: bool
        :param json: Should the Senate's JSON source be loaded?
        :type json: bool
        :param days: How many days of XML data should be loaded? If None, will continue until both a CONVENE and ADJOURN
        event have been found.
        :type days: int
        :return:
        """

        # Load the JSON.
        if json:
            event_count = self._load_json()
            if event_count == 1:
                noun = 'event'
            else:
                noun = 'events'
            self._logger.info(f"Loaded {event_count} {noun} from JSON.")

        # Try the XML. XML usually isn't published until the day after, so this is only useful for the previous day's
        # adjournment. Still, try today, maybe that will change.
        # This will start with today's date and try each successive previous day until two days worth of data are loaded.
        if xml:
            i = 0
            days_loaded = 0
            done_loading = False
            while done_loading is False:
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
                    if event_count == 1:
                        noun = 'event'
                    else:
                        noun = 'events'
                    self._logger.info(f"Loaded {event_count} {noun} from journal on "
                                      f"{(datetime.now() - timedelta(days=i)).strftime('%d %b %Y')}")

                    days_loaded += 1
                i += 1

                # Check for end condition, based on the input options.
                if days is None:
                    if (self._search_events(types=chambers.const.CONVENE) is not None and
                       self._search_events(types=chambers.const.ADJOURN) is not None):
                        done_loading = True
                else:
                    if days_loaded >= days:
                        done_loading = True
            self._logger.info(f"Loaded {days_loaded} days of Senate XML data.")


        self._logger.info("Sorting events.")
        self._sort_events()
        # self._trim_event_log()
        self._updated = datetime.now(tz=self._dctz)
        self._logger.info("Load complete.")
        self._next_update = self._set_next_update()
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
            event_type = chambers.const.CONVENE_SCHEDULED
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
        try:
            senate_tree = ET.fromstring(floor_proceedings)
        except ET.ParseError as xmlerror:
            self._logger.error(f"Could not parse XML from source {source_url}. Received error '{xmlerror}'. Skiping.")
            return 0
        # Pull out the base date. This has to get combined with the time later.
        base_date = datetime.strptime(senate_tree.find('date_iso_8601').text, '%Y-%m-%d').replace(tzinfo=self._dctz)
        self._logger.debug(f"Extracted base date {base_date}")

        # Parse the Intro Text for a convening *time*
        # Search and pull out the text. This has information about convening.
        try:
            intro_text = senate_tree.find("intro_text").text
        except AttributeError:
            self._logger.debug("File has no 'intro_text', nothing usable here.")
            return 0
        else:
            convene_event = self._parse_intro_text(intro_text, base_date, source_url)
            if convene_event is not None:
                new_events.append(convene_event)


        # Check for a 'recess' or 'adjournment' at the end of the activity.
        recess = senate_tree.find("section[@type='recess']/content")
        if recess is not None:
            recess_events = self._parse_recess(recess.text, base_date, source_url)
            new_events.extend(recess_events)
            # depart_type = chambers.const.RECESS_TIME
            # depart_string = recess

        # Check for adjournment. This shouldn't happen at the same time as a recess.
        adjournment = senate_tree.find("section[@type='adjournment']/content")
        if isinstance(adjournment, ET.Element):
            adjournment_events = self._parse_adjournment(adjournment.text, base_date, source_url)
            new_events.extend(adjournment_events)
            # depart_type = chambers.const.ADJOURN
            # depart_string = adjournment

        # Check for convinfo
        # convinfo = senate_tree.find("convinfo")


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

    def _parse_adjournment(self, adjournment_text, base_date, source_url):
        """ Parse an adjournment action.

        :param adjournment_text: The text from the Senate's adjournment item.
        :type adjournment_text: str
        :param base_date: Base date for the events.
        :type base_date: datetime.datetime
        :param source_url: The URL this data came from, to be baked into the event.
        :type source_url: str
        :returns: List of events to add. Empty if no events to add.
        :rtype: list
        """
        new_events = []
        adjournment_text = adjournment_text.replace("\n", "")
        self._logger.debug(f"Adjournment text is '{adjournment_text}'")
        adjournment_time = self._time_from_senate_string(adjournment_text, 'at')

        # if "Under the authority of the order of" in adjournment_text:
        #     # When adjourned at a previous date, we need to adjust the base date.
        #     adjourn_date_search = re.search("order of\\s*\\w*,\\s*(\\w*)\\s*(\\d*),\\s*(\\d{4})", adjournment_text)
        #     adjourn_date = self._date_from_senate_string(
        #         adjourn_date_search.group(1),
        #         adjourn_date_search.group(2),
        #         adjourn_date_search.group(3)
        #     )
        #     adjourn_at = datetime.combine(adjourn_date, adjournment_time).replace(tzinfo=self._dctz)
        # else:
        adjourn_at = datetime.combine(base_date, adjournment_time).replace(tzinfo=self._dctz)

        adjournment_event = {
            'timestamp': adjourn_at,
            'type': chambers.const.ADJOURN,
            'description': adjournment_text,
            'source': 'XML',
            'source_url': source_url
        }
        new_events.append(adjournment_event)

        convene_event = self._parse_next_convening(adjournment_text, base_date, source_url)
        if convene_event is not None:
            new_events.append(convene_event)

        return new_events

    def _parse_intro_text(self, intro_text, base_date, source_url):
        """ Parse the intro text item. This should have the convening.

        :param intro_text: The text from the Senate's intro_text item.
        :type intro_text: str
        :param base_date: Base date for the events.
        :type base_date: datetime.datetime
        :param source_url: The URL this data came from, to be baked into the event.
        :type source_url: str
        :returns: Event to add
        :rtype: dict
        """
        intro_text = intro_text.replace('\n','')
        self._logger.debug(f"Parsing intro text '{intro_text}'")
        convene_time = self._time_from_senate_string(intro_text, "to order at")
        if convene_time is not None:
            convene_dt = datetime.combine(base_date.date(), convene_time).replace(tzinfo=self._dctz)
            # Make a convene event
            convene_event = {
                'timestamp': convene_dt,
                'type': chambers.const.CONVENE,
                'description': intro_text,
                'source': 'XML',
                'source_url': source_url
            }

            return convene_event
        else:
            return None

    def _parse_recess(self, recess_text, base_date, source_url):
        """ Parse recess item

        :param recess_text: The text from the Senate's recess item.
        :type recess_text:
        :param base_date: Base date for the events.
        :type base_date: datetime.datetime
        :returns: List of events to add. Empty if no events to add.
        :rtype: list
        """
        new_events = []
        recess_text = recess_text.replace("\n", "")
        self._logger.info(f"Recess text is '{recess_text}'")
        recess_time = self._time_from_senate_string(recess_text, 'at')
        depart_at = datetime.combine(base_date, recess_time).replace(tzinfo=self._dctz)

        recess_event = {
            'timestamp': depart_at,
            'type': chambers.const.RECESS,
            'description': recess_text,
            'source': 'XML',
            'source_url': source_url
        }
        new_events.append(recess_event)

        convene_event = self._parse_next_convening(recess_text, base_date, source_url)
        if convene_event is not None:
            new_events.append(convene_event)

        return new_events

    def _parse_next_convening(self, depart_text, base_date, source_url):
        """
        Extract the next convening from a recess or adjournment string.

        :param depart_text: The text from the Senate's recess item.
        :type depart_text:
        :param base_date: Base date for the events.
        :type base_date: datetime.datetime
        :param source_url: The URL this data came from, to be baked into the event.
        :type source_url: str
        :returns: List of events to add. Empty if no events to add.
        :rtype: list

        """

        # Find the next convening.
        until_pos = re.search("until", depart_text)
        convening_text = depart_text[until_pos.span()[0]:]
        self._logger.debug(f"Convene text is: {convening_text}")
        convene_time = self._time_from_senate_string(convening_text, 'until')
        self._logger.debug(f"Senate convene time is '{convene_time}'")
        # Does this reference tomorrow?
        if "tomorrow" in convening_text:
            convenes_at = datetime.combine((base_date + timedelta(days=1)).date(), convene_time).replace(tzinfo=self._dctz)
            convenes_event = {
                'timestamp': convenes_at,
                'type': chambers.const.CONVENE_SCHEDULED,
                'description': depart_text,
                'source': 'XML',
                'source_url': source_url
            }
            return convenes_event
        else:
            convene_date_search = re.search("on\\s*\\w*,\\s*(\\w*)\\s*(\\d*),\\s*(\\d{4})", convening_text)
            if len(convene_date_search.groups()) == 3:
                convene_date = self._date_from_senate_string(
                    convene_date_search.group(1),
                    convene_date_search.group(2),
                    convene_date_search.group(3)
                )
                convenes_at = datetime.combine(convene_date, convene_time).replace(tzinfo=self._dctz)
                convenes_event = {
                    'timestamp': convenes_at,
                    'type': chambers.const.CONVENE_SCHEDULED,
                    'description': depart_text,
                    'source': 'XML',
                    'source_url': source_url
                }
                return convenes_event
        return None

    def _date_from_senate_string(self, month_name, day, year):
        """ Extract date from a string

        :param month_name: Name of the month, in English (ie: "June", "July", etc)
        :type month_name: str
        :param day: Day of the month
        :type day: int
        :param year: The year
        :type year: int
        :returns: Date object
        :rtype: datetime.date
        """

        month_names = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12
        }

        # Find the month number. We do this to be locale neutral.
        try:
            month_num = month_names[month_name.lower()]
        except KeyError as ke:
            self._logger.error(f"Month name '{month_name}' not found.")
            raise ke
        else:
            return datetime(month=int(month_num), day=int(day), year=int(year)).date()

    def _time_from_senate_string(self, input_string, prefix):
        """ Extract time from the Senate's string

        :param input_string: String to try to get a time out of.
        :type input_string: str
        :param prefix: Text in front of the time. Usually something like 'to order at' or 'until'.
        :type prefix: str

        :returns: Time object with the time extracted from the text. This is a literal, non-timezone aware time.
        :rtype: datetime.time
        """

        self._logger.debug(f"Trying to extract time from string '{input_string}'")
        search = f"{prefix}\\s*(\\d{{1,2}}:?\\d{{0,2}}) ([a|p]\\s*\\.?m\\s*\\.?)"
        time_search = re.search(search, input_string)

        if time_search is None:
            if 'noon' in input_string:
                ct_string = "12:00 pm"
            else:
                self._logger.warning(f"No usable time found in text '{input_string}'")
                return None
        elif len(time_search.groups()) > 2:
            self._logger.warning(f"Too many times in text '{input_string}'")
            return None
        elif len(time_search.groups()) < 2:
            self._logger.warning(f"No usable time found in text '{input_string}'")
            return None
        else:
            ampm = time_search.group(2).replace('.', '').replace(' ','')
            if ":" in time_search.group(1):
                ct_string = time_search.group(1) + " " + ampm
            else:
                ct_string = time_search.group(1) + ":00 " + ampm

        return datetime.strptime(f"{ct_string}", "%I:%M %p").time()


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