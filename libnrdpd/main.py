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


"""Entry point for the nrdpd program."""

import argparse
import base64
import logging
import logging.handlers
import os.path
import platform
import sys
import stat
import traceback

# Local imports
from . import config
from . import schedule

# My name is
PROGRAM = os.path.basename(sys.argv[0])

# Syslog socket locations. First found is the one used
SYSLOG_SOCKETS = [
    "/dev/log",
    "/var/run/log",
]


def parse_args():
    """Parse command line arguments."""
    random_session = base64.urlsafe_b64encode(os.urandom(9)).decode("utf-8")
    session_id = os.getenv("SESSION_ID", random_session)

    # Default config.ini path
    winpath = os.path.join(
        os.path.dirname(os.path.realpath(sys.argv[0])), "config.ini"
    )
    posixpath = "/etc/nrdpd/config.ini"
    cfgpath = winpath if platform.system() == "Windows" else posixpath

    # Default path to conf.d directory

    winpath = os.path.join(
        os.path.dirname(os.path.realpath(sys.argv[0])), "conf.d"
    )
    posixpath = "/etc/nrdpd/conf.d"
    confd = winpath if platform.system() == "Windows" else posixpath

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        dest="debug",
        default=False,
        action="store_true",
        help="Turn on debug output",
    )
    parser.add_argument(
        "--debug-log",
        dest="debug_log",
        default=None,
        help="Specify a file for debug output. Implies --debug",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        default=False,
        action="store_true",
        help="Turn on verbose output",
    )
    parser.add_argument(
        "--log",
        dest="output_log",
        default=None,
        help="Specify a log file to log debug data to",
    )
    parser.add_argument(
        "--session-id",
        dest="session_id",
        default=session_id,
        help="Specify a session id for syslog logging",
    )
    if platform.system() != "Windows":
        parser.add_argument(
            "-p",
            "--pid-file",
            dest="pidfile",
            default="/var/run/nrdpd.pid",
            help="Pid file location [Default: %(default)s]",
        )
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        default=cfgpath,
        help="Configuration file [Default: %(default)s]",
    )
    parser.add_argument(
        "-C",
        "--conf.d",
        dest="confd",
        default=confd,
        help="Path to conf.d directory for overrides. [Default: %(default)s]",
    )
    opts = parser.parse_args()
    if opts.debug_log:
        opts.debug = True

    # Make sure it exists for testing later.
    if platform.system() == "Windows":
        opts.pidfile = None
    return opts


def main(opts):
    """Core running logic for the program."""
    log = logging.getLogger(f"{__name__}.main")
    log.debug("Start")

    if opts.pidfile:
        try:
            with open(opts.pidfile, "w", encoding="utf-8") as pidfile:
                pidfile.write(str(os.getpid()))
        except OSError as err:
            log.error("Unable to create pid file: %s", err)
            sys.exit(5)

    cfg = config.Config(opts.config, opts.confd)
    sched = schedule.Schedule(cfg)

    sched.loop()


def start():
    """Entry point for pybuild process."""
    opts = parse_args()

    if platform.system() == "Windows":
        syslog = logging.handlers.NTEventLogHandler(PROGRAM)
        syslog.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            f"%(name)s[%(process)d]: {opts.session_id} %(message)s"
        )
        syslog.setFormatter(formatter)
    else:
        sock_location = "/dev/log"  # unconditional default
        for location in SYSLOG_SOCKETS:
            try:
                info = os.stat(location, follow_symlinks=True)
            except FileNotFoundError:
                continue

            if stat.S_ISSOCK(info.st_mode):
                sock_location = location
                break
        # Set up a syslog output stream
        syslog = logging.handlers.SysLogHandler(sock_location)
        syslog.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            f"{PROGRAM}[%(process)d]: %(name)s {opts.session_id} %(message)s"
        )
        syslog.setFormatter(formatter)

    stderr = logging.StreamHandler(stream=sys.stderr)
    if opts.debug:
        if opts.debug_log:
            stderr.setLevel(logging.DEBUG)
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                filename=opts.debug_log,
                filemode="w",
                handlers=[syslog, stderr],
            )
        else:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                handlers=[syslog, stderr],
            )

    elif opts.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s: %(message)s",
            handlers=[syslog, stderr],
        )

    else:
        logging.basicConfig(
            level=logging.ERROR,
            format="%(asctime)s %(name)s: %(message)s",
            handlers=[syslog],
        )

    log = logging.getLogger(PROGRAM)
    log.setLevel(logging.ERROR)

    try:
        log.error("Startup")
        main(opts)
        log.error("Shutdown")
    except Exception as err:  # pylint: disable=W0703
        sys.stderr.write(f"{err}\n")
        if opts.debug:
            traceback.print_exc()
        sys.exit(1)


# vim: filetype=python:

if __name__ == "__main__":
    start()
