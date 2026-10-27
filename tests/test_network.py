import io
import json
import urllib.error

import pytest

from aqj import net, notify, updates


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing requests instead of touching the network."""
    calls = []
    reply = {"body": b"{}"}

    def fake_urlopen(req, timeout):
        calls.append(req)
        if isinstance(reply["body"], Exception):
            raise reply["body"]
        return FakeResponse(reply["body"])

    monkeypatch.setattr(net, "urlopen", fake_urlopen)
    return calls, reply


def test_ntfy_is_sent_as_json_with_unicode_title(sent):
    calls, _ = sent
    notify.send_ntfy("aqj-test", "Ви в черзі", "Спроб: 3")
    req = calls[0]
    assert req.full_url == "https://ntfy.sh"
    body = json.loads(req.data)
    assert body == {
        "topic": "aqj-test",
        "title": "Ви в черзі",
        "message": "Спроб: 3",
        "priority": 4,
        "tags": ["video_game"],
    }
    assert req.get_header("User-agent").startswith("ArmaQueueJoiner/")


def test_ntfy_needs_a_topic(sent):
    with pytest.raises(ValueError):
        notify.send_ntfy("", "t", "m")


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://discord.com/api/webhooks/123/abc-DEF_1", True),
        ("https://discordapp.com/api/webhooks/123/abc", True),
        ("https://ptb.discord.com/api/webhooks/1/x", True),
        ("http://discord.com/api/webhooks/123/abc", False),
        ("https://evil.example/api/webhooks/123/abc", False),
        ("https://discord.com/api/webhooks/abc/abc", False),
        ("", False),
    ],
)
def test_discord_webhook_validation(url, ok):
    assert notify.is_discord_webhook(url) is ok


def test_discord_post(sent):
    calls, _ = sent
    notify.send_discord("https://discord.com/api/webhooks/1/tok", "hello")
    assert json.loads(calls[0].data) == {"content": "hello", "username": "Queue Joiner"}


def test_discord_rejects_other_urls(sent):
    calls, _ = sent
    with pytest.raises(ValueError):
        notify.send_discord("https://example.com/hook", "hi")
    assert calls == []


def test_http_error_becomes_neterror(sent):
    _, reply = sent
    reply["body"] = urllib.error.HTTPError("u", 404, "nope", {}, None)  # type: ignore[arg-type]
    with pytest.raises(net.NetError, match="404"):
        net.request("https://example.com")


def test_offline_becomes_neterror(sent):
    _, reply = sent
    reply["body"] = urllib.error.URLError("offline")
    with pytest.raises(net.NetError, match="no connection"):
        net.request("https://example.com")


@pytest.mark.parametrize(
    "a, b, newer",
    [
        ("2.1.0", "2.0.0", True),
        ("v2.0.1", "2.0.0", True),
        ("2.0", "2.0.0", False),
        ("2.0.0", "2.0.0", False),
        ("1.9.9", "2.0.0", False),
        ("2.10.0", "2.9.0", True),
        ("3.0.0-beta", "2.9.9", True),
    ],
)
def test_version_compare(a, b, newer):
    assert updates.is_newer(a, b) is newer


def test_latest_release_newer(sent):
    _, reply = sent
    reply["body"] = json.dumps(
        {"tag_name": "v999.0.0", "html_url": "https://github.com/x/y/releases/v999.0.0"}
    ).encode()
    release = updates.latest_release()
    assert release == updates.Release("999.0.0", "https://github.com/x/y/releases/v999.0.0")


@pytest.mark.parametrize(
    "payload",
    [
        {"tag_name": "v1.0.0", "html_url": "https://github.com/x"},
        {"tag_name": "v9.0.0", "html_url": "https://evil.example/x"},
        {"tag_name": "v9.0.0", "html_url": "https://github.com/x", "prerelease": True},
        [],
    ],
)
def test_latest_release_ignored(sent, payload):
    _, reply = sent
    reply["body"] = json.dumps(payload).encode()
    assert updates.latest_release() is None


def test_dropped_connection_becomes_neterror(sent):
    import http.client

    _, reply = sent
    reply["body"] = http.client.RemoteDisconnected("closed")
    with pytest.raises(net.NetError):
        net.request("https://example.com")


def test_background_always_reports_back():
    import threading

    done = threading.Event()
    result = {}

    def job():
        raise KeyError("unexpected")

    def on_done(value, error):
        result["error"] = error
        done.set()

    net.in_background(job, on_done)
    assert done.wait(2)
    assert isinstance(result["error"], KeyError)
