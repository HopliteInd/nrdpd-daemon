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
import socket
import typing
import urllib.parse

# Local imports
from . import error
from . import util


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Check:
    """Class describing an individual check.

    Parameters:
        name: Check name.  This is the name that is submitted to nagios and
            must be in sync with the nagios config files.  This name is case
            sensitive.
        command (list of str): The command to execute.  Each element is
            evaluated for variable substitution.
        timeout: How long in seconds to allow a check to run before terminating
            it and reporting CRITICAL due to timeout.
        frequency: How often in seconds the check should run.

    Raises:
        :class:`error.ConfigError`:
            Raised if timeout or frequency are not able to be treated as
            float values.  ``.err`` attribute is set to
            :class:`VALUE_ERROR <error.Err>`
    """

    def __init__(
        self,
        name: str,
        command: list,
        timeout: float,
        frequency: int,
    ):
        self._name = str(name)
        self._fake_it = False
        self._host = None

        try:
            self._timeout = util.min_float_val(timeout, 1.0, "timeout")
            self._frequency = util.min_float_val(frequency, 10.0, "frequency")
        except error.ConfigError as err:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                "[check:%s] %s" % (self._name, err.msg),
            )
        self._command = command

    @property
    def name(self):
        """str: Read only. Name of the check.

        This value is the same as is in the nagios config file.  It's case
        sensitive and can only be set during object creation.
        """

        return self._name

    @property
    def timeout(self):
        """float: Read only. Execution time before timeout and going CRITICAL.

        Once this time value has been hit, the individual check process
        is terminated and CRITICAL is reported back to nagios.
        """

        return self._timeout

    @property
    def frequency(self):
        """float: Read only. The check should run every X seconds."""
        return self._frequency

    @property
    def command(self):
        """list of str: Read only. A 'new' list of the command to run.

        Any template variables have not been filled out yet.  See
        :class:`libnrdpd.task.Task` for handling of templates.
        """
        return self._command

    @property
    def fake(self):
        """bool: Send fake successful results.  This is to allow overriding
        of templates where the template may be invalid for a host.  For
        instance it allows you to generically check disk space on /var/log
        but if a host doesn't have that partition, you can send a fake
        success in to bypass it.
        """
        return self._fake_it

    @fake.setter
    def fake(self, value):
        if not isinstance(value, bool):
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                "[check:%s] fake must be a boolean" % (self._name),
            )
        self._fake_it = value

    @property
    def host(self):
        """str or None: Override the host on a per check basis.
        This allows you to override the hostname for a given check.  This
        doesn't override the hostname the check is being submitted to,
        but instead allows you to use the hostname in a template variable
        with the check.

        For instance if you have a web server with a virtual host, you can
        define the virtual host here to use in the check command line.
        """
        return self._host

    @host.setter
    def host(self, value):
        if not isinstance(value, str) and value is not None:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                "[check:%s] host must be a str or None" % (self._name),
            )
        self._host = value


class Config:  # pylint: disable=R0902
    """Configuration class for nrdpd.

    Parameters:
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
        # Default hostname comes from socket
        self._fqdn = socket.gethostname()
        self._hostname = self._fqdn.split(".")[0]
        self._cacert = None
        self._ip = util.getip()

        self._cp = configparser.ConfigParser(interpolation=None)
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

        # Depends on the upper to to validate that "[config]" exists.
        # Ternary operator handles "" as well as None when evaluating
        # True.
        hostname = self._cp["config"].get("host")
        self._hostname = hostname if hostname else self._hostname
        log.debug("Hostname: %s", self._hostname)
        fqdn = self._cp["config"].get("fqdn")
        self._fqdn = fqdn if fqdn else self._fqdn
        log.debug("FQDN: %s", self._fqdn)
        cacert = self._cp["config"].get("cacert")
        self._cacert = cacert if cacert else None
        log.debug("CA Certificate: %s", self._cacert)

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

            timeout = self._cp[section].get("timeout", 10.0)
            frequency = self._cp[section].get("frequency", 60.0)
            command = self._get_req_opt(section, "command", shlex.split)
            state = self._cp[section].get("state", "enable")
            host = self._cp[section].get("host")
            if host == "":
                host = None

            if state not in ["enable", "disable", "fake"]:
                raise error.ConfigError(
                    error.Err.VALUE_ERROR,
                    "check [%s] state is invalid" % (section),
                ) from None

            if state != "disable":
                self._checks[name] = Check(name, command, timeout, frequency)
                self._checks[name].fake = state == "fake"
                self._checks[name].host = host

    @property
    def checks(self):
        """dict of str, :class:`Check`: Dictionary describing checks to be run.

        Using this property will create a duplicate dictionary that
        you can modify without affecting the internal data structres within
        this class.  The individual :class:`Check` objects can be modified
        within their contstaints.
        """
        return {x: self._checks[x] for x in self._checks}

    @property
    def servers(self):
        """list of str: Urls for servers to publish NRDP results to."""
        return [str(x) for x in self._servers]

    @property
    def token(self):
        """str: Server authentication token."""
        return str(self._token)

    @property
    def host(self):
        """str: Host name presented to nagios.

        By default this will be the short name.   If you want a fully qualified
        domain name add it to the config file.
        """
        return str(self._hostname)

    @property
    def fqdn(self):
        """str: FQDN for inclusion in check varible substitution."""
        return str(self._fqdn)

    @property
    def ip(self):  # pylint: disable=C0103
        """:class:`util.IP`: IP address of the machine"""
        return self._ip

    @property
    def cacert(self):  # pylint: disable=C0103
        """str or None: CA certificate file if specified in the config"""
        return self._cacert
