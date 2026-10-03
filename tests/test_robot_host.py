import subprocess
import sys
import types

import pytest

from companion.robot import RobotSession


def test_reachable_uses_the_sdk_address_when_host_is_blank(monkeypatch) -> None:
    session = RobotSession({"robot_host": ""})
    seen: dict[str, list[str]] = {}

    def fake_run(cmd, **_kwargs):
        seen["cmd"] = cmd

        class _Proc:
            returncode = 0

        return _Proc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert session._robot_reachable() is True
    assert seen["cmd"][-1] == "172.31.1.1"


def test_connect_uses_the_sdk_address_when_host_is_blank(monkeypatch) -> None:
    session = RobotSession({"robot_host": "", "dry_run": False})
    captured: dict[str, tuple] = {}

    class _Client:
        def __init__(self, robot_addr, **_kwargs) -> None:
            captured["addr"] = robot_addr
            raise RuntimeError("stop before the network")

    fake = types.ModuleType("pycozmo")
    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "pycozmo", fake)
    with pytest.raises(RuntimeError, match="stop before the network"):
        session._do_connect()
    assert captured["addr"] == ("172.31.1.1", 5551)
