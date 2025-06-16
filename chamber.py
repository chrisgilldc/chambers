"""
Chamber base class.
"""

import logging
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
        # Base DC timezone, since we need this a lot.
        self._dctz = zoneinfo.ZoneInfo('America/New_York')

    @property
    def activity(self):
        """
        Current floor activity. If that detail is not available, will return None.

        :return:
        """
        raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def adjourned_at(self):
        """
        When the chamber adjourned. Returns datetime if adjourned, None if in session.

        :return: datetime or None
        """

        raise NotImplemented("Must be implemented by a specific base class.")

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

        raise NotImplemented("Must be implemented by a specific base class.")

    @property
    def convenes_at(self):
        """
        When the chamber will convene next. Returns a datetime if adjourned and a reconvening is set, None otherwise.

        :return: datetime or None
        """

        raise NotImplemented("Must be implemented by a specific base class.")

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

    def update(self, force=False):
        """
        Perform an update of data sources.

        :param force: Update all data sources, ignoring and resetting all refresh timers.
        :type force: bool
        :return: datetime
        """
        raise NotImplemented("Must be implemented by a specific base class.")