# Copyright 2020 Hoplite Industries, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Exceptions and error codes for nrdpd."""

import enum
import sys


class Status(enum.Enum):
    """Nagios statuses."""
    OK = 0
    WARN = 1
    CRITICAL = 2
    UNKNOWN = 3


class Err(enum.Enum):
    """Enumeration of errors.

    The primary purpose of this enum is to add a level of sub errors
    to the exceptions in this library.
    """

    # Network Errors
    # -------------------------------------------

    NO_CONNECT = enum.auto()
    """Error establishing network connection."""

    # Configuration Errors
    # -------------------------------------------

    TYPE_ERROR = enum.auto()
    """Parameter type is invalid for the function."""

    VALUE_ERROR = enum.auto()
    """The value is invalid for the use case."""

    REQUIRED_MISSING = enum.auto()
    """A required option is missing."""

    # General Errors
    # -------------------------------------------

    PARSE_ERROR = enum.auto()
    """ Parsing error encountered """

    NOT_FOUND = enum.auto()
    """ Requested entity was not found """

    PERMISSION_DENIED = enum.auto()
    """ Permission was denied for the request """


class NrdpdError(Exception):
    """Base exception for all exceptions emitted from libnrdp

    Parameters:
        err: Value from  the enum :class:`Err`
        msg: Error message

    Attributes:
        err: Value from the enum :class:`Err`
        msg: Error message

    """

    def __init__(self, err: Err, msg: str):
        super().__init__()
        if not isinstance(err, Err):
            raise ValueError("err is not a member of %s.Err" % (__name__))
        self.err = err
        self.msg = msg

    def __str__(self):
        return "[%s] %s" % (self.err.name, self.msg)

    def __repr__(self):
        return "%s.%s(Err.%s, %s)" % (
            __name__,
            self.__class__.__name__,
            self.err.name,
            repr(self.msg),
        )


class NetworkError(NrdpdError):
    """Raised on network errors."""


class ConfigError(NrdpdError):
    """Raised on errors related to the configuration file"""


class NagiosStatus(Exception):
    """Nagios Check API related exception.

    Parameters:
        code (:class:`Status`): Valid Nagios exit code.  ``int`` values also
            work.  Values must be in the range 0-3.
        error: Error message to give to nagios.

    Raises:
        ValueError
            Raised when code passed in is not a valid :class:`Status` value.

    """
    def __init__(self, code: Status, error: str):
        super().__init__()
        self._code = Status(code)
        self._error = error

    @property
    def code(self):
        return self._code

    @property
    def error(self):
        return self._error

    def __str__(self):
        return "%s: %s" % (Status(self._code).name, self._error)

    def __repr__(self):
        return "%s.NagiosStatus(%d, %s)" % (__name, self._code, repr(self._error))

class Ok(NagiosStatus):
    """Nagios status for a successful run.

    As an exception this is likely not useful, but it's here for completeness.
    """
    def __init__(self, error: str):
        super().__init__(Status.OK, error)

class Warn(NagiosStatus):
    """Indicating a check is in a WARNING status."""
    def __init__(self, error: str):
        super().__init__(Status.WARN, error)

class Critical(NagiosStatus):
    """Indicating a check is in a CRITICAL status."""
    def __init__(self, error: str):
        super().__init__(Status.CRITICAL, error)

class Unknown(NagiosStatus):
    """Indicating a check is in a UNKNOWN status."""
    def __init__(self, error):
        super().__init__(Status.UNKNOWN, error)
