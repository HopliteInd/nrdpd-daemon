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

"""If writing your own wrapper around librndpd you should likely start here.
The primary object to interact with is :class:`Config`.  From there you can
use that configuration object to execute checks and submit the results.
"""


import configparser
import glob
import io
import logging
import os.path
import re
import shlex
import typing
import urllib.parse

# Local imports
from . import error


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Check:
    """Class describing an individual check.

    Params:
        name: Check name.  This is the name that is submitted to nagios and
            must be in sync with the nagios config files.  This name is case
            sensitive.
    """

    def __init__(self, name: str):
        self._name = str(name)
        self._timeout = 10.0
        self._delay = 300
        self._command = None

    @property
    def name(self):
        """Name of the check (read only).

        This value is the same as is in the nagios config file.  It's case
        sensitive and can only be set during object creation.
        """

        return self._name

    @property
    def timeout(self):
        """How long to run execute the check for before going CRITICAL.

        This value is the same as is in the nagios config file.  It's case
        sensitive and can only be set during object creation.
        """

        return self._name

    @timeout.setter
    def timeout(self, value):
        if isinstance(value, int):
            tmp = float(value)
        elif isinstance(value, float):
            tmp = value
        else:
            raise error.ConfigError(
                error.Err.TYPE_ERROR,
                "timeout for %s must be a number" % (self._name),
            )
        if tmp <= 1.0:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                "timeout for %s must be greater than 1.0" % (self._name),
            )

        self._timeout = tmp


class Config:
    """Configuration class for nrdpd.

    Params:
        cfgfile: Path to the nrdpd config.ini file.  The value passed in may
            be either a ``str`` or an open file like object derived from
            ``io.IOBase``.

        confd (str or  None): Optional path to the conf.d directory.  Any
            files matching the pattern ``*.ini`` within that directory will
            be processed, possibly overriding existing values. The priority
            on the files is that they are processed in lexical order, with
            later files having the possibility to override earlier ones.
    """

    def __init__(
        self,
        cfgfile: typing.Union[str, io.IOBase],
        confd: typing.Optional[str] = None,
    ):
        log = logging.getLogger("%s.__init__" % __name__)
        log.debug("start")

        self._servers = []  # List of servers to publish to
        self._token = None  # Server authentication token

        self._cp = configparser.ConfigParser()
        self._check_re = re.compile("^[-: a-zA-Z0-9]+")

        self._checks = {}  # Dictionry of checks.  key = name, value = Check

        try:
            if isinstance(cfgfile, str):
                with open(cfgfile, "r") as fobj:
                    self._cp.read_file(fobj)
            elif isinstance(cfgfile, io.IOBase):
                self._cp.read_file(cfgfile)
            else:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    "Invalid cfgfile type: %s" % type(cfgfile),
                )
            if confd is not None:
                if os.path.isdir(confd):
                    extra = sorted(glob.glob(os.path.join(confd, "*.ini")))
                    self._cp.read(extra)

        except FileNotFoundError as err:
            print(err.filename)
            raise error.ConfigError(
                error.Err.NOT_FOUND, "Config file not found: %s" % err.filename
            )
        except PermissionError as err:
            raise error.ConfigError(
                error.Err.PERMISSION_DENIED,
                "Permission was denied processing config file: %s"
                % err.filename,
            )
        except configparser.Error as err:
            raise error.ConfigError(
                error.Err.PARSE_ERROR, "Error parsing config file: %s" % err
            )

        self._get_configuration()
        self._get_checks()

    def _get_req_opt(
        self, section: str, option: str, cast: typing.Callable = str
    ) -> any:
        """Get a required option (must be have a value) from the config file.

        Parameters:
            section: INI file section to pull the option from
            option: INI option to get the value of
            cast (callable): Function to transform the value
                (int, str, shelx.split).  Should raise ``ValueError`` on an
                error with the conversion.

        Returns:
            (any)  Return value is a converted value from what ever ``cast``
                does.

        Raises:
            :class:`error.ConfigError` raised when a configuration anomoly is
                detected.

        """
        if section not in self._cp:
            raise error.ConfigError(
                error.Err.REQUIRED_MISSING,
                "Required section [%s] missing from configuration file"
                % section,
            )

        if option not in self._cp[section]:
            raise error.ConfigError(
                error.Err.REQUIRED_MISSING,
                "Required option [%s]->%s missing from configuration file"
                % (section, option),
            )

        value = self._cp[section][option]

        if not value:
            raise error.ConfigError(
                error.Err.REQUIRED_MISSING,
                "Required option [%s]->%s is empty" % (section, option),
            )

        try:
            value = cast(value)
        except ValueError as err:
            raise error.ConfigError(
                error.Err.TYPE_ERROR,
                "Required option [%s]->%s invalid type: %s"
                % (section, option, err),
            )
        return value

    def _get_configuration(self):
        """Pull our configuration bits out of the config file."""
        log = logging.getLogger("%s._get_configuration" % __name__)
        log.debug("start")

        self._servers = self._get_req_opt("config", "servers", shlex.split)
        self._token = self._get_req_opt("config", "token")

        # Validate values
        for server in self._servers:
            try:
                obj = urllib.parse.urlparse(server)
                if obj.scheme not in ["http", "https"]:
                    raise ValueError(
                        "URL scheme must be 'http' or 'https' not %s"
                        % repr(obj.scheme)
                    )
            except ValueError as err:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    "[config]->servers invalid URL: %s: %s" % (server, err),
                ) from None

    def _get_checks(self):
        """Loop through the configuration looking for service checks."""
        log = logging.getLogger("%s._get_checks" % __name__)
        log.debug("start")
        for section in self._cp:
            if not section.startswith("check:"):
                log.debug("Section [%s] not a check", section)
                continue

            name = section.split(":", 1)[1]
            if not self._check_re.match(name):
                raise error.ConfigError(
                    error.Err.VALUE_ERROR,
                    "check [%s] has an inavlid name" % (section),
                ) from None

            self._checks[name] = Check(name)

    @property
    def checks(self):
        """Dictionary of :class:`Check` objects describing checks to be run.

        Using this property will create a duplicate dictionary that
        you can modify without affecting the internal data structres within
        this class.  The individual :class:`Check` objects can be modified
        within their contstaints.
        """
        return {x: self._checks[x] for x in self._checks}

    @property
    def servers(self):
        """(List of str) Urls for servers to publish NRDP results to."""
        return [str(x) for x in self._servers]

    @property
    def token(self):
        """(str) Server authentication token."""
        return str(self._token)
