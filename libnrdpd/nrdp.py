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
import urllib.parse

# Local imports
from . import config
from . import error
from . import task as tasklib

logging.getLogger(__name__).addHandler(logging.NullHandler())


def submit(cfg: config.Config, task: tasklib.Task, send_host: bool = False):
    """Submit a completed task to nagios via nrdp.

    This will submit the request to all servers in the servers
    config.

    Parameters:
        cfg (libnrdpd.config.Config): libnrdpd Config object
        task (:class:`libnrdpd.task.Task`): Completed task that needs to
            be sent to the central nagios server.

        send_host: If ``True`` send a host check result as well.

    Raises:
        :class:`libnrdpd.error.NotComplete`: Raised when an uncompleted
            task is passed in.
    """
    log = logging.getLogger(f"{__name__}.submit" % __name__)
    if task.expired:
        # Manufacture fake CRITICAL submission results
        code = error.Status.CRITICAL
        message = (
            f"TIMEOUT: Plugin timed out after {task.elapsed:0.2f} seconds"
        )

    else:
        if task.stderr:
            # This must be first in order to accommodate for the
            # possibility that we can't fork a sub process.  Being first
            # allows us to bypass a bunch of other assumptions.

            # If we get output on stderr this is a failure of the
            # API contract.  Report it as an error.
            code = error.Status.CRITICAL
            message = f"Check failed with stderr output:\n{task.stderr}"
        elif task.status is None:
            raise error.NotComplete(
                error.Err.INCOMPLETE,
                (
                    f"{__name__}.submit called with an uncompleted task "
                    f"[check:{task.check.name}]"
                ),
            )

        elif task.status < 0:
            # A signal killed the process
            code = error.Status.CRITICAL
            message = f"Check died with signal {abs(code)}"

        else:
            # Normal processing
            try:
                code = error.Status(task.status)
                message = task.stdout
                log.debug("STDOUT: %s", task.stdout)
            except ValueError:
                code = error.Status.CRITICAL
                message = f"Check exited with unknown code: {task.status}"

    check_results = {
        "checkresults": [
            {
                "checkresult": {"type": "service"},
                "hostname": task.check.hostname,
                "servicename": task.check.name,
                "state": code.value,
                "output": message,
            },
        ]
    }

    if send_host:
        check_results["checkresults"].append(
            {
                "checkresult": {"type": "host"},
                "hostname": task.check.hostname,
                "state": "0",
                "output": "Host alive",
            }
        )

    payload = {
        "cmd": "submitcheck",
        "token": cfg.token,
        "json": json.dumps(check_results),
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    log.debug("payload = %s", repr(payload))

    for url in cfg.servers:
        try:
            with urllib.request.urlopen(
                url, timeout=60, data=data, cafile=cfg.cacert
            ) as req:

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
