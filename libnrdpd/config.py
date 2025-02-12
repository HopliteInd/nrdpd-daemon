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
import ipaddress
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
        log = logging.getLogger(f"{__name__}.{__class__.__name__}")
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
                with open(cfgfile, "r", encoding="utf-8") as fobj:
                    self._cp.read_file(fobj)
            elif isinstance(cfgfile, io.IOBase):
                self._cp.read_file(cfgfile)
            else:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    f"Invalid cfgfile type: {type(cfgfile)}",
                )
            if confd is not None:
                if os.path.isdir(confd):
                    extra = sorted(glob.glob(os.path.join(confd, "*.ini")))
                    self._cp.read(extra)

        except FileNotFoundError as err:
            raise error.ConfigError(
                error.Err.NOT_FOUND, f"Config file not found: {err.filename}"
            )
        except PermissionError as err:
            raise error.ConfigError(
                error.Err.PERMISSION_DENIED,
                f"Permission denied processing config file: {err.filename}",
            )
        except configparser.Error as err:
            raise error.ConfigError(
                error.Err.PARSE_ERROR, f"Error parsing config file: {err}"
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
                (
                    f"Required section [{section}] missing from "
                    "configuration file"
                ),
            )

        if option not in self._cp[section]:
            raise error.ConfigError(
                error.Err.REQUIRED_MISSING,
                (
                    f"Required option [{section}]->{option} missing from "
                    "configuration file"
                ),
            )

        value = self._cp[section][option]

        if not value:
            raise error.ConfigError(
                error.Err.REQUIRED_MISSING,
                f"Required option [{section}]->{option} is empty",
            )

        try:
            value = cast(value)
        except ValueError as err:
            raise error.ConfigError(
                error.Err.TYPE_ERROR,
                f"Required option [{section}]->{option} invalid type: {err}",
            )
        return value

    def _get_configuration(self):
        """Pull our configuration bits out of the config file."""
        log = logging.getLogger(f"{__name__}._get_configuration")
        log.debug("start")

        self._servers = self._get_req_opt("config", "servers", shlex.split)
        self._token = self._get_req_opt("config", "token")

        # Depends on the upper to to validate that "[config]" exists.
        # Ternary operator handles "" as well as None when evaluating
        # True.

        # Check host first.  As it'll be used as the default for hostname
        self._host = util.empty(self._cp["config"].get("host"), self._hostname)
        log.debug("Host: %s", repr(self._host))

        # hostname has precedence the order and defaults set that up
        # This allows for the deprecation of host in favor of hostname
        self._hostname = util.empty(
            self._cp["config"].get("hostname"), self._host
        )
        log.debug("Hostname: %s", self._hostname)

        self._fqdn = util.empty(self._cp["config"].get("fqdn"), self._fqdn)
        log.debug("FQDN: %s", self._fqdn)

        self._cacert = util.empty(self._cp["config"].get("cacert"))
        log.debug("CA Certificate: %s", self._cacert)

        ipaddr = util.empty(self._cp["config"].get("ip"))
        if ipaddr:
            try:
                self._ip = ipaddress.ip_address(ipaddr).compressed
            except (ipaddress.AddressValueError, ValueError) as err:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    f"[config]->ip invalid IP address: {ipaddr}: {err}",
                ) from None
        log.debug("ip address: %s", self._ip)

        # Validate values
        for server in self._servers:
            try:
                obj = urllib.parse.urlparse(server)
                if obj.scheme not in ["http", "https"]:
                    raise ValueError(
                        "URL scheme must be 'http' or 'https' not "
                        f"{repr(obj.scheme)}"
                    )
            except ValueError as err:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    f"[config]->servers invalid URL: {server}: {err}",
                ) from None

    def _get_checks(self):
        """Loop through the configuration looking for service checks."""
        log = logging.getLogger(f"{__name__}._get_checks")
        log.debug("start")
        for section in self._cp:
            if not section.startswith("check:"):
                log.debug("Section [%s] not a check", section)
                continue

            name = section.split(":", 1)[1]
            if not self._check_re.match(name):
                raise error.ConfigError(
                    error.Err.VALUE_ERROR,
                    f"check [{section}] has an inavlid name",
                ) from None

            timeout = self._cp[section].getfloat("timeout", 10.0)
            frequency = self._cp[section].getfloat("frequency", 60.0)
            command = self._get_req_opt(section, "command", shlex.split)
            state = util.empty(self._cp[section].get("state"), "enable")
            host = util.empty(self._cp[section].get("host"))
            hostname = util.empty(self._cp[section].get("hostname"))
            fqdn = util.empty(self._cp[section].get("fqdn"))
            ipaddr = util.empty(self._cp[section].get("ip"))

            if state not in ["enable", "disable", "fake"]:
                raise error.ConfigError(
                    error.Err.VALUE_ERROR,
                    f"check [{section}] state is invalid",
                ) from None

            if state != "disable":
                self._checks[name] = Check(
                    name, command, timeout, frequency, self
                )
                self._checks[name].fake = state == "fake"
                self._checks[name].hostname = hostname
                self._checks[name].host = host
                self._checks[name].fqdn = fqdn
                self._checks[name].ip = ipaddr

    @property
    def checks(self):
        """dict of str, :class:`Check`: Dictionary describing checks to be run.

        Using this property will create a duplicate dictionary that
        you can modify without affecting the internal data structres within
        this class.  The individual :class:`Check` objects can be modified
        within their contstaints.
        """

        # Running dict on an existing dictionary duplicates it which is what
        # we want here
        return dict(self._checks)

    @property
    def servers(self):
        """list of str: Urls for servers to publish NRDP results to."""
        return [str(x) for x in self._servers]

    @property
    def token(self):
        """str: Server authentication token."""
        return str(self._token)

    @property
    def hostname(self):
        """str: Host name presented to nagios.

        By default this will be the short name.   If you want a fully qualified
        domain name add it to the config file.
        """
        return str(self._hostname)

    @property
    def host(self):
        """(deprecated) str: Host name presented to nagios.

        By default this will be the short name.   If you want a fully qualified
        domain name add it to the config file.  If "hostname" is set it will
        be used instead.
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


class Check:  # pylint: disable=too-many-instance-attributes
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
        config: Config class instance for outer config.

    Raises:
        :class:`error.ConfigError`:
            Raised if timeout or frequency are not able to be treated as
            float values.  ``.err`` attribute is set to
            :class:`VALUE_ERROR <error.Err>`
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        name: str,
        command: list,
        timeout: float,
        frequency: int,
        config: Config,
    ):
        self._name = str(name)
        self._fake_it = False
        self._host = None
        self._hostname = None
        self._fqdn = None
        self._ip = None
        self._config = config

        if not isinstance(config, Config):
            raise TypeError("config must be a Config instance")

        try:
            self._timeout = util.min_float_val(timeout, 1.0, "timeout")
            self._frequency = util.min_float_val(frequency, 10.0, "frequency")
        except error.ConfigError as err:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                f"[check:{self._name}] {err.msg}",
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
        """bool: Send fake successful results.

        This is to allow overriding of templates where the template may be
        invalid for a host.  For instance it allows you to generically check
        disk space on /var/log but if a host doesn't have that partition,
        you can send a fake success in to bypass it.
        """
        return self._fake_it

    @fake.setter
    def fake(self, value):
        if not isinstance(value, bool):
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                f"[check:{self._name}] fake must be a boolean",
            )
        self._fake_it = value

    @property
    def hostname(self):
        """str or None: Override the nagios hostname on a per check basis.

        This allows you to override the hostname for a given check.  This
        overrides the hostname the check is being submitted for.
        """
        return util.empty(self._hostname, self._config.hostname)

    @hostname.setter
    def hostname(self, value):
        if not isinstance(value, str) and value is not None:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                f"[check:{self._name}] hostname must be a str or None",
            )
        self._hostname = value

    @property
    def host(self):
        """str or None: Override the host on a per check basis.

        This allows you to override the host for a given check.  This
        doesn't override the hostname the check is being submitted to,
        but instead allows you to use the hostname in a template variable
        with the check.

        For instance if you have a web server with a virtual host, you can
        define the virtual host here to use in the check command line.
        """
        return util.empty(self._host, self._config.host)

    @host.setter
    def host(self, value: typing.Union[str, None]):
        if not isinstance(value, str) and value is not None:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                f"[check:{self._name}] host must be a str or None",
            )
        self._host = value

    @property
    def ip(self):  # pylint: disable=invalid-name
        """str or None: Override the ip on a per check basis.

        This allows you to override the ip for a given check.
        """
        return util.empty(self._ip, self._config.ip)

    @ip.setter
    def ip(
        self, value: typing.Union[None, str]
    ):  # pylint: disable=invalid-name
        if value is not None:
            try:
                value = ipaddress.ip_address(value).compressed
            except (ipaddress.AddressValueError, ValueError) as err:
                raise error.ConfigError(
                    error.Err.TYPE_ERROR,
                    (
                        f"[check:{self._name}]->ip invalid IP address: "
                        f"[{value}]: {err}"
                    ),
                ) from None
        self._ip = value

    @property
    def fqdn(self):
        """str or None: Override the fqdn on a per check basis.

        This allows you to override the fqdn for a given check.
        """
        return util.empty(self._fqdn, self._config.fqdn)

    @fqdn.setter
    def fqdn(self, value):
        if not isinstance(value, str) and value is not None:
            raise error.ConfigError(
                error.Err.VALUE_ERROR,
                f"[check:{self._name}] fqdn must be a str or None",
            )
        self._fqdn = value
