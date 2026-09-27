from companion.access import client_allowed


def test_private_is_the_default() -> None:
    assert client_allowed("192.168.0.13", None)
    assert client_allowed("192.168.0.13", "")
    assert client_allowed("10.1.2.3", "private")
    assert client_allowed("172.16.4.4", "private")
    assert client_allowed("127.0.0.1", "private")
    assert not client_allowed("8.8.8.8", "private")
    assert not client_allowed("1.1.1.1", None)


def test_local_is_only_this_machine() -> None:
    assert client_allowed("127.0.0.1", "local")
    assert client_allowed("::1", "127.0.0.1")
    assert not client_allowed("192.168.0.13", "local")
    assert not client_allowed("10.0.0.2", "localhost")


def test_cidr_and_all() -> None:
    assert client_allowed("192.168.0.20", "192.168.0.0/24")
    assert client_allowed("127.0.0.1", "192.168.0.0/24") is False
    assert not client_allowed("192.168.1.20", "192.168.0.0/24")
    assert client_allowed("8.8.8.8", "all")
    assert client_allowed("192.168.1.9", "local,192.168.1.0/24")
