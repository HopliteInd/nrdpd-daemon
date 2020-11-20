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

"""Funcitons for submitting results to the NRDP endpiont."""

import json
import logging
import urllib.error
import urllib.request

# Local imports
from . import config
from . import error
from . import task as tasklib

logging.getLogger(__name__).addHandler(logging.NullHandler())


def submit(cfg: config.Config, task: tasklib.Task):
    """Submit a completed task to nagios via nrdp.

    This will submit the request to all servers in the servers
    config.

    Parameters:
        cfg (libnrdpd.config.Config): libnrdpd Config object
        task (:class:`libnrdpd.task.Task`): Completed task that needs to
            be sent to the central nagios server.

    Raises:
        :class:`libnrdpd.error.NotComplete`: Raised when an uncompleted
            task is passed in.
    """
    log = logging.getLogger("%s.Nrdp.submit" % __name__)
    if task.expired:
        # Manufacture fake CRITICAL submission results
        code = error.Status.CRITICAL
        message = "TIMEOUT: Plugin timed out after %0.2f seconds" % (
            task.elapsed
        )

    else:
        if task.stderr:
            # This must be first in order to accommodate for the
            # possibility that we can't fork a sub process.  Being first
            # allows us to bypass a bunch of other assumptions.

            # If we get output on stderr this is a failure of the
            # API contract.  Report it as an error.
            code = error.Status.CRITICAL
            message = "Check failed with stderr output:\n%s" % (task.stderr)
        elif task.status is None:
            raise error.NotComplete(
                error.Err.INCOMPLETE,
                "%s.Nrdp.submit called with an uncompleted task [check:%s]"
                % (__name__, task.check.name),
            )

        elif task.status < 0:
            # A signal killed the process
            code = error.Status.CRITICAL
            message = "Check died with signal %d" % abs(code)

        else:
            # Normal processing
            try:
                code = error.Status(task.status)
                message = task.stdout
            except ValueError:
                code = error.Status.CRITICAL
                message = "Check exited with unknown code: %d" % (task.status)

    check_results = {
        "checkresults": [
            {
                "checkresult": {"type": "host"},
                "hostname": cfg.host,
                "state": "0",
                "output": "Host alive enough to send this",
            },
            {
                "checkresult": {"type": "service"},
                "hostname": cfg.host,
                "servicename": task.check.name,
                "state": str(code),
                "output": message,
            },
        ]
    }

    payload = {
        "cmd": "submitcheck",
        "token": cfg.token,
        "json": json.dumps(check_results),
    }

    for url in cfg.servers:
        try:
            req = urllib.request.urlopen(url, timeout=60, data=payload)

            httpstatus = req.getcode()
            if httpstatus != 200:
                log.error(
                    "Submission to %s failed http status: %d",
                    url,
                    httpstatus,
                )
        except urllib.error.URLError as err:
            log.error("Submission to %s failed: %s", url, err)
            continue
