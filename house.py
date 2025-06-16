"""
House current status and calendar
"""
import time

import chambers.const
from .chamber import Chamber
from datetime import datetime, timedelta, timezone
import logging
from operator import itemgetter
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

    def __init__(self, parent_logger=None, log_level= logging.INFO):
        """
        Base chamber object.
        :param parent_logger: Parent logger, if any.
        :param log_level: Log level.
        """
        super().__init__("House", parent_logger, log_level)
        self._updated = datetime(1900, 1, 1, 0, 0, 0, tzinfo=self._dctz)

        self.load()

    def update(self, force=False):
        """
        Update house events, and prune.
        Returns the datetime of the next time an update should happen.

        :param force: Update all data sources, ignoring and resetting all refresh timers.
        :type force: bool
        :return: datetime
        """

        if force or len(self._events) == 0:
            # Always load if we're forced, or if we don't have any data yet.
            self.load()
        else:
            since_update = ( datetime.now(self._dctz) - self._updated ).seconds
            if not self.convened:
                if self.convenes_at is not None:
                    # If we're within 10 minutes of the convening time, update once a minute.
                    if (self.convenes_at - timedelta(minutes=10) ) < datetime.now(timezone.utc) and since_update > 60:
                        self.load()
                else:
                    if since_update > 600:
                        self.load()
            else:
                if since_update > 120:
                    self.load()


    @property
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

        for event in self._events:
            if selected_event is None:
                selected_event = event
            elif event['timestamp'] <= target_dt and event['timestamp'] > selected_event['timestamp']:
                selected_event = event
        return selected_event

    @property
    def adjourned_at(self):
        """
        When the chamber adjourned. Returns datetime if adjourned, None if in session.

        :return: datetime or None
        """

        latest_convene = self._search_events(types=chambers.const.CONVENE)
        latest_adjourn = self._search_events(types=chambers.const.ADJOURN)
        if latest_adjourn['timestamp'] > latest_convene['timestamp']:
            return latest_adjourn['timestamp']
        else:
            return None

    @property
    def convened(self):
        """
        Is the House convened?
        :return:
        """

        latest_convene = self._search_events(types=chambers.const.CONVENE)
        latest_adjourn = self._search_events(types=chambers.const.ADJOURN)
        if latest_adjourn is not None and latest_convene is None:
            # If we have an adjourn record but not a convene record.
            return False
        elif latest_adjourn['timestamp'] < latest_convene['timestamp']:
            return True
        else:
            return False

    @property
    def convened_at(self):
        """
        When the chamber convened for its main session. Does *not* consider Recesses. Will return Datetime if convened,
        None if adjourned.

        :return: datetime or None
        """
        if self.convened:
            latest_convene = self._search_events(types=chambers.const.CONVENE)
            return latest_convene['timestamp']
        else:
            return None

    @property
    def convenes_at(self):
        """
        When the chamber will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.

        :return: datetime or None
        """

        next_convene = self._search_events(search_forward=True, types=chambers.const.CONVENE_SCHEDULED)
        if next_convene is not None:
            return next_convene['timestamp']
        else:
            return None

    def load(self):
        """
        Load current House activity.
        """

        # Try to load today. Will 404 if House isn't in session yet.
        today_response = requests.get(House.URL_BASE + datetime.now().strftime('%Y%m%d') + ".xml")
        if today_response.ok:
            self._logger.info("Loading today's House floor proceedings.")
            # Response is okay, process it.
            self._load_xml(today_response.content)

        # Load previous day's
        i = 1
        found_response = False
        while not found_response:
            old_response = requests.get(House.URL_BASE + (datetime.now() - timedelta(days=i) ).strftime('%Y%m%d') + ".xml")
            if old_response.ok:
                self._logger.info("Found floor proceedings for {}. Loading.".format(
                    (datetime.now() - timedelta(days=i)).strftime('%d %b %Y')
                ))
                # pprint(old_response.content)
                self._load_xml(old_response.content)
                found_response = True
            i += 1
        self._sort_events()
        # self._trim_event_log()
        self._updated = datetime.now(self._dctz)

    def _load_xml(self, house_xml):
        """
        Load a single XML file.


        :param house_xml: The XML file from the House Floor site.
        :type house_xml: str
        :return: Number of items added or replaced.
        :rtype: int
        """

        house_tree = ET.fromstring(house_xml)
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
            elif floor_action.tag == 'floor_action':
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
                elif event['act-id'] == 'H8D000':
                    if 'MORNING-HOUR DEBATE' in event['description']:
                        event['type'] = chambers.const.MORNING_DEBATE
                    elif 'DEBATE - ' in event['description']:
                        event['type'] = chambers.const.DEBATE_BILL
                        event['action_item'] = floor_action.find('action_item').text
                    else:
                        event['type'] = chambers.const.OTHER
                elif event['act-id'] == 'H37100':
                    event['type'] = chambers.const.VOTE_RECORDED
                    event['action_item'] = floor_action.find('action_item').text
                elif event['act_id'] == 'H35000':
                    event['type'] = chambers.const.VOTE_VOICE
                    event['action_item'] = floor_action.find('action_item').text
                # Add to the event log.
                self._events.append(event)
        return True

    def _search_events(self, timestamp=None, search_forward=False, types=None):
        """
        Search for events based on critera.

        :param timestamp: Timestamp to use as a reference. Defaults to now.
        :param timestamp: datetime or None
        :param search_forward: Search for future events if set. By default, will only search for past events.
        :type search_forward: bool
        :param types: Types of events to include. If not specified, will search all.
        :type types: list or int
        :return:
        """
        # self._logger.debug("Available events: {}".format(self._events))
        # self._logger.debug("Timestamp: {}".format(timestamp))
        # self._logger.debug("Search Forward: {}".format(search_forward))
        # self._logger.debug("Types: {}".format(types))

        selected_event = None
        # Input checking.
        if isinstance(timestamp, datetime):
            target_dt = timestamp
        else:
            target_dt = datetime.now(timezone.utc)

        if types is None:
            types = chambers.const.ALL_EVENTS
        elif type(types) in (str, int):
            # If a string, make it a list of one.
            types = [types]

        for event in self._events:
            # print("Checking event: {}".format(event))
            try:
                if event['type'] in types:
                    if search_forward and event['timestamp'] >= target_dt:
                        if selected_event is None:
                            selected_event = event
                        elif event['timestamp'] < selected_event['timestamp']:
                            selected_event = event
                    elif not search_forward and event['timestamp'] <= target_dt:
                        if selected_event is None:
                            selected_event = event
                        elif event['timestamp'] > selected_event['timestamp']:
                            selected_event = event
            except KeyError:
                self._logger.warning("Event {} does not have type setting.".format(event['id']))
                self._logger.warning("Event dump - {}".format(event))
        return selected_event

    def _sort_events(self):
        """
        Sort the list of events by timestamp.

        :return:
        """
        self._events = sorted(self._events, key=itemgetter('timestamp'), reverse=True)

    def _trim_event_log(self):
        """
        Trim the event log.

        :return:
        """
        delete_targets = []
        limit = datetime.now(timezone.utc) - timedelta(days=1)
        limit = limit.replace(hour=0,minute=0,second=0,microsecond=0)
        self._logger.info("Considering all events older than {}".format(limit))
        i = 0
        while i < len(self._events):
            if self._events[i]['timestamp'] < limit:
                delete_targets.append(i)
            i += 1

        self._logger.info("Will remove {} events.".format(len(delete_targets)))
        for item in sorted(delete_targets, reverse=True):
            if item > 2:
                self._events.pop(item)
