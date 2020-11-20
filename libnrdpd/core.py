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

"""Core scheduling and execution."""

import io
import logging
import shlex
import string
import subprocess
import time

from . import error
from . import config


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Task:
    """Definition of a task to run in the scheduler."""

    def __init__(self, check: config.Check):
        self._check = check
        self.reset()

    def reset(self):
        """Reset task so it can be run again.

        Call this when you have completed processing a given run of a task.
        """
        self._child = None
        self._began = None
        self._ended = None
        self._running = False

    def start(self, **kwargs):
        """Start the execution of the check associated with this task.

        Convert the variables in the command from the check into something
        that can be used in ``os.execvp``.

        Params:

            kwargs: Template variables to fill in.
        """
        log = logging.getLogger("%s.run" % __name__)

        # Apply template variables
        cmd = []
        for element in self._check.command:
            temp = string.Template(element)
            cmd.append(temp.safe_substitute(kwargs))

        log.info("Running check: %s", " ".join([shlex.quote(x) for x in cmd]))
        try:
            self._child = subprocess.Popen(
                cmd,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
            )
            self._running = True
            self._began = time.time()
        except OSError as err:
            log.error("Unable to run [check:%s]: %s", self._check.name, err)
            raise error.Critical(
                "Unable to execute [check:%s]: %s" % (self._check.name, err)
            )

    @property
    def running(self):
        """bool: Tell if the task is currently running.

        Keep checking this value to see if the process has stopped.  Each
        check of this value will initiate an output check and process that
        output of any was found.
        """
        retval = False
        if self._child:
            status = self._child.poll()
            retval = True if status is None else False
        return retval

    @property
    def status(self):
        """int or None: The exit code for the process.

        * ``None``:  The Task hasn't processed the execution status yet.
        * Positive ``int``: The exit status of the check.  To be valid
            with the Nagios API this must be in the range 0-3.
        * Negative ``int``: The nagios check exited with a signal.  The abs()
            value of this is the signal that it terminated with.
        """
        return self._child.returncode if self._child else None

    @property
    def check(self):
        """:class:`config.Check`: The Check associated with this task."""
        return self._check

    @property
    def began(self):
        """float: Time when the current run of the check began.

        Before the process has started this will be ``None``.  Once a
        process has been started this will be a float indicating the
        start time for the current run.

        """
        return self._began

    @property
    def ended(self):
        """float or None: Time when the "current" run of the check ended.

        A value of ``None`` indicates that the Task hasn't detected
        that the process has ended yet.
        """
        return self._ended

    @property
    def expired(self):
        """bool: Tells if a check has exceeded it's timeout value."""
        retval = False
        if self._child:
            # We can only be expired if a child has been started
            if self._ended is None:
                elapsed = time.time() - self._began
            else:
                elapsed = self._ended - self._began
            if elapsed > self._check.timeout:
                retval = True
        return retval


class Schedule:
    """Handle scheduling of checks"""

    def __init__(self):
        self._checks = {}
        self._running = {}
        self._queue = []
