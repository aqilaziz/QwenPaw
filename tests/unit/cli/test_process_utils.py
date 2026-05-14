# -*- coding: utf-8 -*-
# pylint: disable=protected-access
from __future__ import annotations

from types import SimpleNamespace

import pytest

from qwenpaw.cli import process_utils


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (12, 12),
        ("34", 34),
        ("not-int", None),
        (1.2, None),
    ],
)
def test_coerce_optional_int(value: object, expected: int | None) -> None:
    assert process_utils._coerce_optional_int(value) == expected


def test_parse_windows_process_snapshot_json_handles_object_and_list() -> None:
    payload = """
    [
      {
        "ProcessId": "100",
        "ParentProcessId": "10",
        "Name": "python.exe",
        "CommandLine": "python -m qwenpaw app --port 9000"
      },
      {"ProcessId": "bad", "Name": "ignored"}
    ]
    """

    assert process_utils._parse_windows_process_snapshot_json(payload) == {
        100: (10, "python.exe", "python -m qwenpaw app --port 9000"),
    }
    assert not process_utils._parse_windows_process_snapshot_json("")
    assert not process_utils._parse_windows_process_snapshot_json("{bad")
    assert process_utils._parse_windows_process_snapshot_json(
        '{"ProcessId": 101, "Name": "qwenpaw.exe"}',
    ) == {101: (None, "qwenpaw.exe", "")}


def test_parse_windows_process_snapshot_csv() -> None:
    payload = (
        "Node,CommandLine,Name,ParentProcessId,ProcessId\n"
        'DESKTOP,"qwenpaw app --port=7777",qwenpaw.exe,50,200\n'
        "DESKTOP,ignored,ignored.exe,bad,bad\n"
    )

    assert process_utils._parse_windows_process_snapshot_csv(payload) == {
        200: (50, "qwenpaw.exe", "qwenpaw app --port=7777"),
    }
    assert not process_utils._parse_windows_process_snapshot_csv("")


def test_process_table_parses_unix_ps_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(process_utils.sys, "platform", "linux")

    def fake_run(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            stdout="  12 python -m qwenpaw app\nbad row\n  13\n",
        )

    monkeypatch.setattr(process_utils.subprocess, "run", fake_run)

    assert process_utils._process_table() == [
        (12, "python -m qwenpaw app"),
        (13, ""),
    ]


def test_process_table_returns_empty_when_ps_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(process_utils.sys, "platform", "linux")

    def fail(*_args: object, **_kwargs: object) -> None:
        raise process_utils.subprocess.TimeoutExpired("ps", 10)

    monkeypatch.setattr(process_utils.subprocess, "run", fail)

    assert process_utils._process_table() == []


@pytest.mark.parametrize(
    "command",
    [
        "python -m qwenpaw app",
        "qwenpaw app --host 127.0.0.1",
        "python /pkg/qwenpaw/__main__.py app",
        '"C:/Tools/qwenpaw.exe" app',
        "C:/Tools/qwenpaw.exe app",
    ],
)
def test_matches_qwenpaw_cli_command(command: str) -> None:
    assert process_utils._matches_qwenpaw_cli_command(command, "app")
    assert process_utils._is_qwenpaw_service_command(command)


def test_wrapper_process_matches_name_or_app_desktop_command() -> None:
    assert process_utils._is_qwenpaw_wrapper_process("qwenpaw.exe", "")
    assert process_utils._is_qwenpaw_wrapper_process(
        "python.exe",
        "python -m qwenpaw desktop",
    )
    assert (
        process_utils._is_qwenpaw_wrapper_process(
            "python.exe",
            "python -m qwenpaw skills",
        )
        is False
    )


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("qwenpaw app --port 9000", 9000),
        ("qwenpaw app --port=9001", 9001),
        ("qwenpaw app", 8088),
    ],
)
def test_extract_port_from_command(command: str, expected: int) -> None:
    assert process_utils._extract_port_from_command(command) == expected


def test_base_url_wraps_ipv6_hosts() -> None:
    assert (
        process_utils._base_url("127.0.0.1", 8088) == "http://127.0.0.1:8088"
    )
    assert process_utils._base_url(" ::1 ", 8088) == "http://[::1]:8088"
    assert process_utils._base_url("[::1]", 8088) == "http://[::1]:8088"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (None, []),
        ("0.0.0.0", ["127.0.0.1", "localhost", "0.0.0.0"]),
        ("::", ["127.0.0.1", "localhost", "::1", "::"]),
        ("localhost", ["localhost", "127.0.0.1", "::1"]),
        ("192.168.1.2", ["192.168.1.2"]),
    ],
)
def test_candidate_hosts_expands_local_bind_addresses(
    host: str | None,
    expected: list[str],
) -> None:
    assert process_utils._candidate_hosts(host) == expected
