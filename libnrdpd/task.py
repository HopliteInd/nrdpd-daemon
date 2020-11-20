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
import random
import shlex
import string
import subprocess
import time

# Local imports
from . import config


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Task:  # pylint: disable=R0902
    """Definition of a task to run in the scheduler."""

    def __init__(self, check: config.Check):
        if not isinstance(check, config.Check):
            raise ValueError(
                "Type for check %s expected libnrdpd.config.Check"
                % (type(check))
            )
        self._check = check
        self._start = time.time() + (random.random() * 3.0)

        # Make pylint shut it's pie hole.
        self._child = None
        self._began = None
        self._ended = None
        self._running = None
        self._stdout = None
        self._stderr = None
        self._timeout = None

        self.reset()

    def reset(self):
        """Reset task so it can be run again.

        Call this when you have completed processing a given run of a task.
        """
        self._child = None
        self._began = None
        self._ended = None
        self._running = False
        self._stdout = io.StringIO()
        self._stderr = io.StringIO()
        self._timeout = False

        self.reset_start()

    def run(self, **kwargs):
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

        self.reset_start()

        # Set next start time for the queue
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
            self._stderr.write(
                "Unable to execute [check:%s]: %s" % (self._check.name, err)
            )
            self._began = time.time()
            self._ended = time.time()

    def reset_start(self):
        """Set start time for the NEXT check.

        This happens automatically during run() and reset().
        """

        now = time.time()
        if self._start < now:
            self._start = self._start + self._check.frequency
            if self._start < now:
                self._start = now + self._check.frequency

    @property
    def complete(self):
        """bool: Tell if the task has completed.

        Keep checking this value to see if the check has completed.  Each
        check of this value will initiate an output check and process that
        output of any was found.
        """
        retval = True
        if self._child and self._running:
            status = self._child.poll()
            retval = status is not None
            self._running = retval

            try:
                stdout, stderr = self._child.communicate(timeout=0.01)
                if stdout:
                    self._stdout.write(
                        stdout.decode("utf-8", errors="replace")
                    )
                if stderr:
                    self._stderr.write(
                        stderr.decode("utf-8", errors="replace")
                    )
            except subprocess.TimeoutExpired:
                pass

            if self._running:
                if self.expired:
                    self._child.kill()
            else:
                # Process just terminated, so record those things...
                self._ended = time.time()

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
        if self._child and not self._timeout:
            # We can only be expired if a child has been started
            if self._ended is None:
                elapsed = time.time() - self._began
            else:
                elapsed = self._ended - self._began
            if elapsed > self._check.timeout:
                self._timeout = True

        return self._timeout

    @property
    def stdout(self):
        """str or None: stdout from the check."""
        retval = None
        if self._child:
            value = self._stdout.getvalue()
            if value:
                retval = value

        return retval

    @property
    def stderr(self):
        """str or None: stderr from the check.

        A value other than ``None`` is considered a failed check.
        """
        retval = None
        if self._child:
            value = self._stderr.getvalue()
            if value:
                retval = value

        return retval

    @property
    def start(self):
        """float: Next scheduled execution time in epoch time."""
        return self._start

    @property
    def elapsed(self):
        """float: Elapsed execution time.

        This is only valid if the task has been completed.  The value
        will be -1.0 if the task hasn't completed yet.
        """
        if self._ended is not None and self._started is not None:
            retval = self._ended - self._started
        else:
            retval = -1.0
        return retval
