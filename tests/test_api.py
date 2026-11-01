"""The stats client."""

import pytest

from custom_components.unseenet.api import (
    CannotConnect,
    InvalidAuth,
    UnseenetClient,
    UnseenetError,
    UnsupportedVersion,
    parse,
)

from .conftest import TOKEN, load


async def test_node(node_server) -> None:
    snap = await UnseenetClient("127.0.0.1", node_server.port, TOKEN).fetch()
    assert snap.kind == "node"
    assert snap.key == "ed25519:bjhcf6tbf2yt37vn7iomsdg5o4xlvdvudjndnm4prrveiur3cukq"
    assert snap.title == "ha-unseenet"
    assert node_server.requests == ["token", "stats"]


async def test_replica(replica_server) -> None:
    snap = await UnseenetClient("127.0.0.1", replica_server.port, TOKEN).fetch()
    assert snap.kind == "replica"
    assert snap.title == "Unseenet replica s3x2dksm"


async def test_wrong_token(node_server) -> None:
    with pytest.raises(InvalidAuth):
        await UnseenetClient("127.0.0.1", node_server.port, "nope").fetch()


async def test_no_token_where_one_is_needed(node_server) -> None:
    with pytest.raises(UnseenetError):
        await UnseenetClient("127.0.0.1", node_server.port, None).fetch()


async def test_cannot_connect(node_server) -> None:
    port = node_server.port
    await node_server.stop()
    with pytest.raises(CannotConnect):
        await UnseenetClient("127.0.0.1", port, TOKEN).fetch()


def test_versions() -> None:
    snap = load("node")
    snap["v"] = 2
    with pytest.raises(UnsupportedVersion):
        parse(snap)
    with pytest.raises(UnseenetError):
        parse({"v": 1})
    with pytest.raises(UnseenetError):
        parse({"error": "unknown request"})
