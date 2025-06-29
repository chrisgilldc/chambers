"""
Chamber base class.
"""

import chambers.const
from datetime import datetime, timedelta, timezone
import logging
from operator import itemgetter
import zoneinfo
from zoneinfo import ZoneInfo


class Chamber:
    _dctz: ZoneInfo

    def __init__(self, name, parent_logger = None, log_level = logging.WARNING):
        """
        Base chamber object.
        :param name: Chamber name. Probably going to be 'House' or 'Senate'!
        :type name: str
        :param parent_logger: Parent logger, if any.
        :param log_level: Log level.
        """

        # Create a logger for ourselves.
        if parent_logger is None:
            # If no parent detector is given this sensor is being used in a testing capacity. Create a null logger.
            self._logger = logging.getLogger(name)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            console_handler.setLevel(log_level)
            self._logger.addHandler(console_handler)
            self._logger.setLevel(log_level)
        else:
            self._logger = parent_logger.getChild(name)

        # Save inputs.
        self._name = name
        # Initialize variables.
        self._events = [] # Event log.
        self._convened = None
        self._convened_at = None
        self._convenes_at = None
        self._will_convene_at = None
        self._adjourned_at = None

        # Base DC timezone, since we need this a lot.
        self._dctz = zoneinfo.ZoneInfo('America/New_York')
        # Initialize updated as an arbitrarily old date.
        self._updated = datetime(1900, 1, 1, 0, 0, 0, tzinfo=self._dctz)

    @property
    def activity(self):
        """
        Current floor activity. If that detail is not available, will return None.

        :return:
        """
        raise NotImplemented("Must be implemented by a specific base class.")

    # @property
    # def adjourned_at(self):
    #     """
    #     When the chamber adjourned. Returns datetime if adjourned, None if in session.
    #
    #     :return: datetime or None
    #     """
    #
    #     raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def adjourned_at(self):
        """
        When the chamber adjourned. Returns datetime if adjourned, None if in session.

        :return: datetime or None
        """

        latest_convene = self._search_events(types=chambers.const.CONVENE)
        latest_adjourn = self._search_events(types=chambers.const.ADJOURN)
        if latest_adjourn is None:
            return None
        elif latest_adjourn['timestamp'] is not None and latest_convene is None:
            return latest_adjourn['timestamp']
        elif latest_adjourn['timestamp'] > latest_convene['timestamp']:
            return latest_adjourn['timestamp']
        else:
            return None

    @property
    def convened(self):
        """
        Is this chamber currently convened. This is determined based on the best information available.
        Returns None if chamber state is unknown.

        :return: bool or None
        """
        raise NotImplemented("Must be implemented by a specific base class.")

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

    # @property
    # def convened_at(self):
    #     """
    #     When the chamber convened for its main session. Does *not* consider Recesses. Will return Datetime if convened,
    #     None if adjourned.
    #
    #     :return: datetime or None
    #     """
    #
    #     raise NotImplemented("Must be implemented by a specific base class.")
    #
    # @property
    # def convenes_at(self):
    #     """
    #     When the chamber will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.
    #
    #     :return: datetime or None
    #     """
    #
    #     raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def latest(self):
        """
        Latest convening or adjournment action.
        :return: dict
        """
        raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def next(self):
        """
        Next scheduled event, if available. If no next event is available, will return an empty list.
        :return: dict
        """
        raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def next_update(self):
        """
        When the next update is scheduled.
        :return: float or datetime
        """

        if self.convened:
            return self._updated + timedelta(minutes=2)
        else:
            # If we know when the chamber next convenes, the next check should be ten minutes before that.
            if self.convenes_at is not None:
                preconvene_target = self.convenes_at - timedelta(minutes=10)
                if preconvene_target < datetime.now(timezone.utc):
                    return self._updated + timedelta(seconds=60)
                else:
                    return preconvene_target
            else:
                return self._updated + timedelta(minutes=10)

    def update(self, force=False):
        """
        Perform an update of data sources.

        :param force: Update all data sources, ignoring and resetting all refresh timers.
        :type force: bool
        :return: datetime
        """
        raise NotImplemented("Must be implemented by a specific base class.")

    def _load(self):
        """
        Chamber internal load method. Fetches from source(es) and produces correct data.

        :return: None
        """

        raise NotImplemented("Must be implemented by a specific base class.")

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
