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
    """Parsing error encountered."""

    NOT_FOUND = enum.auto()
    """Requested entity was not found."""

    PERMISSION_DENIED = enum.auto()
    """Permission was denied for the request."""

    INCOMPLETE = enum.auto()
    """Task is in an incomplete state."""


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


class NotComplete(NrdpdError):
    """Raised when a task is being used when it's not complete."""


class NetworkError(NrdpdError):
    """Raised on network errors."""


class ConfigError(NrdpdError):
    """Raised on errors related to the configuration file"""
