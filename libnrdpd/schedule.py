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

import json
import logging
import time

# Local imports
from . import config
from . import nrdp
from . import task as tasklib


logging.getLogger(__name__).addHandler(logging.NullHandler())


class Schedule:
    """Handle scheduling of checks

    Parameters:
        cfg (:class:`libnrdpd.config.Config`): Config object

    """

    def __init__(self, cfg: config.Config):
        self._cfg = cfg
        self._tasks = {}
        self._running = {}
        self._queue = []

        for check in self._cfg.checks:
            self._queue.append(tasklib.Task(check))

    def sort(self):
        """Re-sort the queue for processing"""
        self._queue = sorted(self._queue, key=lambda x: x.start)

    def loop(self):
        """Main engine for the nrdpd daemon.

        Run in a loop forever executing checks and submitting them.
        """
        log = logging.getLogger("%s.Schedule.loop" % __name__)
        self.sort()

        while True:
            # Only re-order queue on changes in status
            changed = False

            # Check the status of running children
            # Can't iterate over a dictionary that I'm modifying within
            # the iteration.
            for name in self._running.keys():  # pylint: disable=C0201
                task = self._running[name]

                if task.complete:
                    event = {
                        "check": task.check.name,
                        "started": task.began,
                        "elapsed": task.ended - task.began,
                        "status": task.status,
                        "timeout": task.expired,
                    }

                    log.error("Task complete: %s", json.dumps(event))
                    try:
                        nrdp.submit(self._cfg, task)
                    except Exception as err:  # pylint: disable=W0703
                        log.error("Submission error: %s", err)

                    task.reset()
                    del self._running[name]
                    changed = True

            if changed:
                self.sort()

            now = time.time()
            while self._queue and self._queue[0].start < now:
                task = self._queue[0]
                self._running[task.check.name] = task
                template = {"host": self._cfg.host, "ip": self._cfg.ip}
                task.run(**template)
                self.sort()

            # Delay until the next scheduled check if nothing is running
            # If stuff is running the 100% CPU usage delay is built into
            # checking the running processes and thus no delay is needed
            # here.
            if self._queue and not self._running:
                now = time.time()
                sleepytime = self._queue[0].start - now
                if sleepytime > 0:
                    time.sleep(sleepytime)
