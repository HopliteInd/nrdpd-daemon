import libnrdpd
import pytest
import os.path


# Test loading of a valid config file
def test_config_valid():
    cfg = libnrdpd.config.Config(os.path.join("config", "config-valid.ini"))
    assert cfg.token == "b"
    assert cfg.servers[0] == "http://127.0.0.1:8898/nrdp"

def test_config_valid_overrides():
    cfg = libnrdpd.config.Config(
            os.path.join("config", "config-valid.ini"),
            os.path.join("config","conf.d"),
            )
    assert cfg.token == "g"
    assert cfg.servers[0] == "http://127.0.0.1:8898/nrdp"


def test_config_bad_url():
    with pytest.raises(libnrdpd.error.ConfigError):
        libnrdpd.config.Config(os.path.join("config", "config-bad-url.ini"))
