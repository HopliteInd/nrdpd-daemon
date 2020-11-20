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

"""Supporting utility functions for the librndpd library."""

import ipaddress
import logging
import socket
import typing

# Local imports
from . import error


IPV6_ADDRS = [
    "2620:119:35::35",  # OpenDNS DNS server
    "2001:4860:4860::8888",  # Google Public DNS server
    "2001:4998:44:3507::8001",  # Yahoo.com public IP
    "2600:1409:3800::ace8:c60",  # www.army.mil
    "2600:1406:1a:38d::2add",  # whitehouse.gov
    "2001:1890:1c00:3113::f:3005",  # att.com
]
"""Test addresses for determining host's IPv6 address.

No traffic is sent, just a UDP socket is created so we can determine what
the OS thinks is a good default route IP address.  Many IPs are tested to
acquire a statistical model of the most likely default route.
"""

IPV4_ADDRS = [
    "1.1.1.1",  # cloudflare public DNS server
    "8.8.8.8",  # Google Public DNS server
    "74.6.231.2",  # Yahoo.com public IP
    "23.53.34.25",  # www.army.mil
    "23.10.60.33",  # whitehouse.gov
    "144.160.155.43",  # att.com
]
"""Test addresses for determining host's IPv4 address.

No traffic is sent, just a UDP socket is created so we can determine what
the OS thinks is a good default route IP address.  Many IPs are tested to
acquire a statistical model of the most likely default route.
"""

logging.getLogger(__name__).addHandler(logging.NullHandler())


def min_float_val(value: float, minval: float, name: str):
    """Convert argument to float assuring it meets it's minimal value.

    Params:
        value: Incoming value to convert and validate.
        minval: Minimal value for the float.
        name: Used in exceptions to identify the bad variable.

    Raises:
        :exc:`libnrdpd.error.ConfigError`
            Raised on invalid numbers.  The ``.err`` property is set to
            :class:`TYPE_ERROR <libnrdpd.error.Err>` when conversion to float
            fails.  It is set to :class:`VALUE_ERROR <libnrdpd.error.Err>`
            when the value doesn't meet the ``minval`` minimum value.

    """
    log = logging.getLogger("%s.min_float_val" % __name__)
    log.debug(
        "start: value=%s minval=%s name=%s",
        repr(value),
        repr(minval),
        repr(name),
    )
    try:
        retval = float(value)
    except ValueError as err:
        raise error.ConfigError(
            error.Err.TYPE_ERROR,
            "Value for '%s' must be a number: %s" % (name, err),
        ) from None
    try:
        minimum = float(minval)
    except ValueError as err:
        raise error.ConfigError(
            error.Err.TYPE_ERROR,
            "minval for '%s' must be a number: %s" % (name, err),
        ) from None
    if retval < minimum:
        raise error.ConfigError(
            error.Err.VALUE_ERROR,
            "Value for '%s' must be greater than %0.2f" % (name, minimum),
        )
    return retval


class IP:  # pylint: disable=C0103
    """Class defining the IP address for a host.

    Params:
        ipv4 (str or None): IPv4 address
        ipv6 (str or None): IPv6 address
    """

    def __init__(self, ipv4: typing.Optional[str], ipv6: typing.Optional[str]):
        self._ipv4 = None
        self._ipv6 = None
        if ipv4 is None and ipv6 is None:
            raise error.NrdpdError(
                error.Err.VALUE_ERROR,
                "IP(): At least one of ipv4 or ipv6 must be set",
            )

        if ipv4 is not None:
            try:
                ipaddress.IPv4Address(ipv4)
            except ValueError as err:
                raise error.NrdpdError(
                    error.Err.VALUE_ERROR,
                    "IPv4 address is not valid: %s" % err,
                ) from None
            self._ipv4 = ipv4

        if ipv6 is not None:
            try:
                ipaddress.IPv6Address(ipv6)
            except ValueError as err:
                raise error.NrdpdError(
                    error.Err.VALUE_ERROR,
                    "IPv6 address is not valid: %s" % err,
                ) from None
            self._ipv6 = ipv6

    def __str__(self):
        return self._ipv6 if self._ipv6 else self._ipv4

    def __repr__(self):
        return "%s.IP(%s, %s)" % (__name__, repr(self._ipv4), repr(self._ipv6))

    @property
    def address(self):
        """Default IP address for the host.

        The preference is for IPv6, so if both an IPv6 and IPv4 address are
        defined on the host, it will use the IPv6 address.
        """
        return self._ipv6 if self._ipv6 else self._ipv4

    @property
    def v4(self):
        """IPv4 address if present.

        If no IPv4 address is defined for the host this will return 127.0.0.1.
        This is to make sure configs at least have *something* to report when
        someone forces {ip.v4}.
        """
        return self._ipv4 if self._ipv4 else "127.0.0.1"

    @property
    def v6(self):
        """IPv6 address if present.

        If no IPv6 address is defined for the host this will return ::1.
        This is to make sure configs at least have *something* to report when
        someone forces {ip.v6}.
        """
        return self._ipv6 if self._ipv6 else "::1"


def getip():
    """Determine the IP of the machine.

    Returns:
        :class:`IP`
            Representing the IP address of the box

    Raises:
        :exc:`libnrdpd.error.NrdpdError`
            When no IP is able to be determined.
    """

    log = logging.getLogger("%s.getip" % __name__)

    ipv6 = {}
    for remote in IPV6_ADDRS:
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.connect((remote, 53))
            ip = sock.getsockname()[0]  # pylint: disable=C0103
            if ip not in ipv6:
                ipv6[ip] = 0
            ipv6[ip] += 1
            log.debug(
                "IPv6 address determined to be: %s going to %s", ip, remote
            )
        except OSError as err:
            log.debug("Failed to create IPv6 socket to %s: %s", remote, err)
            continue
    v6addr = None
    for addr in [x[0] for x in sorted(ipv6.items(), key=lambda y: y[1])]:
        test = ipaddress.IPv6Address(addr)
        if test.is_loopback or test.is_link_local:
            continue
        v6addr = test.compressed
        break

    ipv4 = {}
    for remote in IPV4_ADDRS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((remote, 53))
            ip = sock.getsockname()[0]  # pylint: disable=C0103
            if ip not in ipv4:
                ipv4[ip] = 0
            ipv4[ip] += 1
            log.debug(
                "IPv4 address determined to be: %s going to %s", ip, remote
            )
        except OSError as err:
            log.debug("Failed to create IPv4 socket to %s: %s", remote, err)
            continue
    v4addr = None
    for addr in [x[0] for x in sorted(ipv4.items(), key=lambda y: y[1])]:
        test = ipaddress.IPv4Address(addr)
        if test.is_loopback or test.is_link_local:
            continue
        v4addr = str(test)
        break

    return IP(v4addr, v6addr)


# End getip()
