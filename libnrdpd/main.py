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
import os
import os.path
import platform
import sys
import textwrap
import traceback

# Local imports
from . import config
from . import schedule

# My name is
SLIM_SHADY = os.path.basename(sys.argv[0])


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
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        default=cfgpath,
        help="Configuration file",
    )
    parser.add_argument(
        "-C",
        "--conf.d",
        dest="confd",
        default=confd,
        help="Path to conf.d directory for overrides",
    )
    opts = parser.parse_args()
    if opts.debug_log:
        opts.debug = True

    return opts


def main(opts):
    """Core running logic for the program."""
    log = logging.getLogger("%s.main" % __name__)
    log.debug("Start")

    cfg = config.Config(opts.config, opts.confd)
    sched = schedule.Schedule(cfg)

    sched.loop()


def start():
    """Entry point for pybuild process."""
    opts = parse_args()
    log = logging.getLogger(SLIM_SHADY)
    log.addHandler(logging.NullHandler())

    if opts.debug:
        if opts.debug_log:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                filename=opts.debug_log,
                filemode="w",
            )
        else:
            logging.basicConfig(
                level=logging.DEBUG,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )

    elif opts.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)s: %(message)s",
        )

    if platform.system() == "Windows":
        loghandler = logging.handlers.NTEventLogHandler(SLIM_SHADY)
        loghandler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "%(name)s[%(process)d]: {session} %(message)s".format(
                session=opts.session_id
            )
        )
        loghandler.setFormatter(formatter)
        log.addHandler(loghandler)

    else:
        # Set up a syslog output stream
        loghandler = logging.handlers.SysLogHandler("/dev/log")
        loghandler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "%(name)s[%(process)d]: {session} %(message)s".format(
                session=opts.session_id
            )
        )
        loghandler.setFormatter(formatter)
        log.addHandler(loghandler)

    try:
        log.error("Startup")
        main(opts)
        log.error("Shutdown")
    except Exception as err:  # pylint: disable=W0703
        sys.stderr.write("%s\n" % (textwrap.fill(str(err))))
        if opts.debug:
            traceback.print_exc()
        sys.exit(1)


# vim: filetype=python:

if __name__ == "__main__":
    start()
