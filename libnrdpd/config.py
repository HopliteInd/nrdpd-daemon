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

""" Create configuration object for nrdpd. """


import configparser
import io
import logging
import shlex
import typing
import urllib.parse

# Local imports
from . import error


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Config:
    """Configuration class for nrdpd

    Params:
        cfgfile: Path to the nrdpd config.ini file.  The value passed in may
            be either a ``str`` or an open file like object derived from
            ``io.IOBase``.

    """

    def __init__(self, cfgfile: typing.Union[str, io.IOBase]):
        log = logging.getLogger("%s.__init__" % __name__)
        log.debug("start")

        self._servers = []  # List of servers to publish to
        self._token = None  # Server authentication token

        self._cp = configparser.ConfigParser()

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

    def _get_configuration(self):
        """Pull our configuration bits out of the config file"""
        log = logging.getLogger("%s._get_configuration" % __name__)
        log.debug("start")

        self._servers = self._get_req_opt("config", "servers", shlex.split)
        self._servers = self._get_req_opt("config", "token")

        # Validate values
        for server in self._servers:
            try:
                obj = urllib.parse.urlparse(server)
                if obj.scheme not in ["http", "https"]:
                    raise ValueError("URL scheme must be 'http' or 'https'")
            except ValueError as err:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    "[config]->servers invalid URL: %s: %s" % (server, err),
                ) from None

    def _get_checks(self):
        pass

    @property
    def servers(self):
        """(List of str) Urls for servers to publish NRDP results to"""
        return [str(x) for x in self._servers]

    @property
    def token(self):
        """(str) Server authentication token"""
        return str(self._token)
