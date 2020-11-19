# 3rd party
import pytest

# Local
import libnrdpd


def test_IP_v4_good():
    ip = libnrdpd.util.IP("8.8.8.8", None)
    assert ip.address == "8.8.8.8"
    assert ip.v4 == "8.8.8.8"
    assert ip.v6 == "::1"


def test_IP_v6_good():
    ip = libnrdpd.util.IP(None, "2001:4860:4860::8888")
    assert ip.address == "2001:4860:4860::8888"
    assert ip.v4 == "127.0.0.1"
    assert ip.v6 == "2001:4860:4860::8888"


def test_IP_good():
    ip = libnrdpd.util.IP("8.8.8.8", "2001:4860:4860::8888")
    assert ip.address == "2001:4860:4860::8888"
    assert ip.v4 == "8.8.8.8"
    assert ip.v6 == "2001:4860:4860::8888"


def test_IP_none():
    with pytest.raises(libnrdpd.error.NrdpdError):
        libnrdpd.util.IP(None, None)


def test_IP_v4_invalid():
    with pytest.raises(libnrdpd.error.NrdpdError):
        libnrdpd.util.IP("1234", None)


def test_IP_v6_invalid():
    with pytest.raises(libnrdpd.error.NrdpdError):
        libnrdpd.util.IP(None, "2001:::1")


def test_getip():
    ip = libnrdpd.util.getip()
    if (ip.v4 == "127.0.0.1" and ip.v6 == "::1"):
        raise ValueError("Both ipv4 and ipv6 are localhost")


def test_min_float_val_good():
    assert libnrdpd.util.min_float_val("30", "10", "test") == 30.0
    assert libnrdpd.util.min_float_val("30.0", "10.0", "test") == 30.0
    assert libnrdpd.util.min_float_val(60.0, "10", "test") == 60.0
    assert libnrdpd.util.min_float_val(15, 10, "test") == 15.0
    assert libnrdpd.util.min_float_val(15.0, 10.0, "test") == 15.0
    assert libnrdpd.util.min_float_val(15, 10, "test") == 15.0


def test_min_float_val_bad():
    with pytest.raises(libnrdpd.error.ConfigError):
        libnrdpd.util.min_float_val("a", 10, "test")
    with pytest.raises(libnrdpd.error.ConfigError):
        libnrdpd.util.min_float_val(10, "a", "test")
    with pytest.raises(libnrdpd.error.ConfigError):
        libnrdpd.util.min_float_val(10, 20, "test")
