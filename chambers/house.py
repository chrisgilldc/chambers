"""
House current status and calendar
"""
import time

import chambers.const
from .chamber import Chamber
from datetime import datetime, timedelta, timezone
import logging

import requests
import xml.etree.ElementTree as ET

class House(Chamber):
    """
    House current status and calendar
    """
    URL_BASE = "https://clerk.house.gov/floor/"

    # Allowed event types.
    EVENT_TYPES = (
        'convene',
        'adjourn',
        'recess',
        'morning-hour')

    def __init__(self, parent_logger=None, log_level=logging.INFO):
        """
        Base chamber object.
        :param parent_logger: Parent logger, if any.
        :type parent_logger: logging.Logger
        :param log_level: Log level.
        """
        super().__init__("House", parent_logger, log_level)

    def update(self, force=False):
        """
        Update house events, and prune.
        Returns the datetime of the next time an update should happen.

        :param force: Update all data sources, ignoring and resetting all refresh timers.
        :type force: bool
        :return: datetime
        """

        if force:
            # Always load if we're forced, or if we don't have any data yet.
            self._logger.info("Force load set, updating.")
            self._load()
            super()._set_next_update()
            return True
        elif len(self._events) == 0:
            self._logger.info("No events available at update. Loading.")
            self._load()
            self._set_next_update()
            return True
        elif datetime.now(timezone.utc) > self.next_update:
            self._logger.info("Update time has passed. Loading.")
            self._load()
            self._set_next_update()
            return True
        else:
            return False

    def activity(self, timestamp=None):
        """
        Get the current activity based on the event log.

        :param timestamp: The timestamp to check for. If none, will check for now.
        :type timestamp: datetime
        :return:
        """
        selected_event = None

        if isinstance(timestamp, datetime):
            target_dt = timestamp
        else:
            target_dt = datetime.now(timezone.utc)

        if target_dt > datetime.now(timezone.utc):
            selected_event = self._search_events(target_dt, search_forward=True)
        else:
            selected_event = self._search_events(target_dt)

        return selected_event


    # @property
    # @property
    # def convened_at(self):
    #     """
    #     When the chamber convened for its main session. Does *not* consider Recesses. Will return Datetime if convened,
    #     None if adjourned.
    #
    #     :return: datetime or None
    #     """
    #     if self.convened:
    #         latest_convene = self._search_events(types=chambers.const.CONVENE)
    #         return latest_convene['timestamp']
    #     else:
    #         return None
    #
    # @property
    # def convenes_at(self):
    #     """
    #     When the chamber will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.
    #
    #     :return: datetime or None
    #     """
    #
    #     next_convene = self._search_events(search_forward=True, types=chambers.const.CONVENE_SCHEDULED)
    #     if next_convene is not None:
    #         return next_convene['timestamp']
    #     else:
    #         return None

    def _load(self):
        """
        Load current House activity.

        :returns: True if load succeeded. False if a non-fatal error occured.
        :rtype: bool
        """

        # Try to load today. Will 404 if House isn't in session yet.
        try:
            today_response = requests.get(House.URL_BASE + datetime.now().strftime('%Y%m%d') + ".xml")
        except requests.exceptions.ConnectionError as ce:
            self._logger.error(f"Exception while trying to retrieve today's journal - '{ce}'")
            return False
        else:
            if today_response.ok:
                self._logger.info("Loading today's House floor proceedings.")
                # Response is okay, process it.
                event_count = self._load_xml(today_response.content)
                self._logger.info(f"Today's proceedings resulted in {event_count} events.")

        # Load previous day
        i = 1
        found_response = False
        while not found_response:
            old_response = requests.get(House.URL_BASE + (datetime.now() - timedelta(days=i) ).strftime('%Y%m%d') + ".xml")
            if old_response.ok:
                self._logger.info("Found floor proceedings for {}. Loading.".format(
                    (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')
                ))
                # pprint(old_response.content)
                if today_response.ok:
                    self._logger.info("Loading to extract adjournment.")
                    # Load the previous legislative days' XML only to get the adjournment data.
                    event_count = self._load_xml(old_response.content, only_eod=True)
                    if event_count != 1:
                        self._logger.error("Could not load adjournment from journal on {}".format(
                            (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')))
                    else:
                        self._logger.info("Loaded adjournment from journal.")
                else:
                    event_count = self._load_xml(old_response.content)
                    self._logger.info("Loaded {} events from journal on {}".format(event_count,(datetime.now()
                            - timedelta(days=i)).strftime('%d %b %Y') ))
                found_response = True
            i += 1
        self._logger.info("Sorting events.")
        self._sort_events()
        # self._trim_event_log()
        self._updated = datetime.now(self._dctz)
        self._logger.info("Load complete.")
        return True

    def _load_xml(self, house_xml, only_eod=False):
        """
        Load a single XML file.


        :param house_xml: The XML file from the House Floor site.
        :type house_xml: str
        :param only_eod: Only find the end of legislative day record from the XML file, if any.
        :type only_eod: bool
        :return: Number of items added or replaced.
        :rtype: int
        """

        try:
            house_tree = ET.fromstring(house_xml)
        except ET.ParseError as xmlerror:
            self._logger.error(f"Could not parse XML. Received error '{xmlerror}'. Skiping.")
            return 0
        # Get the publication date for this file.
        pubdate = datetime.strptime(house_tree.find('pubDate').text[:-4], "%a, %d %b %Y %H:%M:%S")
        pubdate = pubdate.replace(tzinfo=self._dctz)
        events = []
        # Process all children.
        items = 0
        for floor_action in house_tree.find('floor_actions'):
            if floor_action.tag == 'legislative_day_finished':
                if self._add_end_day(floor_action):
                    items += 1
                    if only_eod:
                        return items # Can return here, since by definition there's only one end of day.
            elif floor_action.tag == 'floor_action' and not only_eod:
                # Breaking this out to make logging for debugging more details.
                if floor_action.attrib['act-id'] == "H20100":
                    self._logger.debug("Floor Action has id H20100 (Convene). Will add.".format(floor_action.attrib['act-id']))
                    if self._add_floor_action(floor_action):
                        items += 1
                elif floor_action.attrib['act-id'] == "H61000":
                    self._logger.debug("Floor Action has id H61000 (Adjourn/Recess). Will add.")
                    if self._add_floor_action(floor_action):
                        items += 1
                elif floor_action.attrib['act-id'] == "H8D000":
                    self._logger.debug("Floor Action has id H8D000 (Debate). Will add.")
                    if self._add_floor_action(floor_action):
                        items += 1
                else:
                    self._logger.debug("Floor Action has had {}. Skipping.".format(floor_action.attrib['act-id']))
        self._logger.info("Processed all floor actions.")
        return items

    def _add_end_day(self, end_day):
        """
        Add the end of day.

        :param end_day:
        :return:
        """

        convenes_dt = datetime.strptime(
            end_day.get('next-legislative-day-convenes'), "%Y%m%dT%H:%M").replace(tzinfo=self._dctz)
        # Create a new future event.
        event = {
            'type': chambers.const.CONVENE_SCHEDULED,
            'timestamp': convenes_dt
        }
        event['id'] = event['timestamp'].timestamp()
        self._events.append(event)


    def _add_floor_action(self, floor_action):
        """
        Add a floor action to the events log.

        :return: True if added, false if not.
        :rtype: bool
        """
        do_add = False
        # Decide if this action *should* be added. Prevents duplicates.
        if len(self._events) == 0:
            do_add = True
        else:
            i = 0
            del_list = []
            while i < len(self._events):
                if self._events[i]['id'] == floor_action.get('unique-id'):
                    self._logger.debug("Floor action {} is already in event (item {})".format(floor_action.get('unique-id'),i))
                    # Have to do a DT conversion here.
                    fa_dt = datetime.strptime(floor_action.get('update-date-time'), "%Y%m%dT%H:%M").replace(tzinfo=self._dctz)
                    if fa_dt > self._events[i]['updated']:
                        # If the new floor action matches an existing one and has a newer update, replace.
                        self._logger.debug("Floor action newer than existing one. {} vs {}. Will replace.".
                                          format(fa_dt, self._events[i]['updated']))
                        del_list.append(i)
                        do_add = True
                        break
                    else:
                        self._logger.debug("Floor action not newer than existing. {} vs {}. Will not replace.".
                                          format(fa_dt, self._events[i]['updated']))
                        return False
                else:
                    do_add = True
                i += 1


        if do_add:
            if floor_action.tag == 'floor_action':
                event = {
                    'id': floor_action.get('unique-id'), # The unique ID of this action.
                    'act-id': floor_action.get('act-id'), # Preserving the act-id. May need this? TBD.
                    'updated': datetime.strptime(floor_action.get('update-date-time'),
                                                 "%Y%m%dT%H:%M").replace(tzinfo=self._dctz),
                    # The action time lives in a child element action_time element. The for-search has an ISO8601 time.
                    'timestamp': datetime.strptime(floor_action.find('action_time').get('for-search'),
                                               "%Y%m%dT%H:%M:%S").replace(tzinfo=self._dctz),
                    'description': floor_action.find('action_description').text.strip()
                }

                if floor_action.get('act-id') == 'H20100': # Convenings
                    if 'The House convened, returning from a recess' in event['description']:
                        self._logger.info("Event {} - Return from Recess.".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.RECONVENE
                    elif 'The House convened, starting a new legislative day.' in event['description']:
                        self._logger.info("Event {} - New Legislative Day.".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.CONVENE
                elif floor_action.get('act-id') == 'H61000':
                    # Adjourn
                    if 'The House adjourned.' in event['description']:
                        self._logger.info("Event {} - Adjournment.".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.ADJOURN
                    elif 'The Speaker announced that the House do now adjourn pursuant to clause 13 of Rule I' in event['description']:
                        self._logger.info("Event {} - Adjournment".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.ADJOURN
                    elif 'The Speaker announced that the House do now recess. The next meeting is scheduled for' in event['description']:
                        self._logger.info("Event {} - Recess to time.".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.RECESS_TIME
                    elif 'The Speaker announced that the House do now recess. The next meeting is subject to the call of the Chair.' == event['description']:
                        self._logger.info("Event {} - Recess to call of chair.".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.RECESS_COC
                    elif 'The Speaker announced that the House do now recess for a period of less than 15 minutes.':
                        self._logger.info("Event {} - Recess for less than 15m".format(floor_action.get("act-id")))
                        event['type'] = chambers.const.RECESS_15M
                elif event['act-id'] == 'H8D000':
                    if 'MORNING-HOUR DEBATE' in event['description']:
                        event['type'] = chambers.const.MORNING_DEBATE
                    elif 'DEBATE - ' in event['description']:
                        event['type'] = chambers.const.DEBATE_BILL
                        event['action_item'] = floor_action.find('action_item').text
                    else:
                        event['type'] = chambers.const.OTHER
                elif event['act-id'] == 'H37100':
                    self._logger.info("Event {} - Recorded Vote".format(floor_action.get("act-id")))
                    event['type'] = chambers.const.VOTE_RECORDED
                    event['action_item'] = floor_action.find('action_item').text
                elif event['act_id'] == 'H35000':
                    self._logger.info("Event {} - Voice Vote".format(floor_action.get("act-id")))
                    event['type'] = chambers.const.VOTE_VOICE
                    event['action_item'] = floor_action.find('action_item').text
                # Add to the event log.
                self._events.append(event)
        return True


