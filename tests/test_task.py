# 3rd party
import os.path
import pytest
import platform

# Local
import libnrdpd


@pytest.mark.skipif(platform.system() == "Windows", reason="Needs /bin/sh")
def test_Task():
    cfg = libnrdpd.config.Config(os.path.join("config", "config-valid.ini"))
    task = libnrdpd.task.Task(cfg.checks["test"])

    task.run()

    while True:
        if task.complete:
            break

    assert task.status == 1
    assert task.stderr == None
    assert "Uhh.." in task.stdout
