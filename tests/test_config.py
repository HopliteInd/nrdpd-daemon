import socket
import os.path

# 3rd party
import pytest

# Local
import libnrdpd

DEF_TIMEOUT = 10.0
DEF_FREQUENCY = 60.0

# Test loading of a valid config file
def test_config_valid():
    cfg = libnrdpd.config.Config(os.path.join("config", "config-valid.ini"))
    assert cfg.token == "b"
    assert cfg.servers[0] == "http://127.0.0.1:8898/nrdp"
    assert cfg.host == socket.gethostname().split(".")[0]

    for name, check in cfg.checks.items():
        assert check.timeout == DEF_TIMEOUT
        assert check.frequency == DEF_FREQUENCY


# Test loading valid config with overrides in conf.d files
def test_config_valid_overrides():
    cfg = libnrdpd.config.Config(
        os.path.join("config", "config-valid.ini"),
        os.path.join("config", "conf.d"),
    )
    assert cfg.token == "g"
    assert cfg.servers[0] == "https://127.0.0.1:99/nrdp"
    assert cfg.servers[1] == "https://127.0.0.1:77/nrdp"
    assert cfg.host == "i.love.roses"

    for name, check in cfg.checks.items():
        if name == "test":
            assert check.timeout == 60.0
            assert check.frequency == 600.0
        else:
            assert check.timeout == 15.0
            assert check.frequency == 120.0


# Test loading valid minimally viable product config file.
def test_config_valid_mvp():
    cfg = libnrdpd.config.Config(
        os.path.join("config", "config-mvp.ini"),
    )
    assert cfg.token == "mvp"
    assert cfg.servers[0] == "http://127.0.0.1:9999/nrdp"
    assert cfg.host == socket.gethostname().split(".")[0]

    for name, check in cfg.checks.items():
        assert check.timeout == DEF_TIMEOUT
        assert check.frequency == DEF_FREQUENCY


def test_config_bad_url():
    with pytest.raises(libnrdpd.error.ConfigError):
        libnrdpd.config.Config(os.path.join("config", "config-bad-url.ini"))
