"""
Shell exceptions to categorize and catch exceptions.
"""

class ChamberException(Exception):
    pass

class ChamberExceptionRecoverable(ChamberException):
    pass

class ChamberExceptionFatal(ChamberException):
    pass