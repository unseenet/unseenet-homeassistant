"""A small client for the stats interface of an Unseenet node or council replica.

The interface is the one ``unseenet-monitor`` uses: one request line, one JSON
line back (unseenet/unseenet ``src/unseenet/node/stats.py``). Reached over Home
Assistant's add-on network, a connection first proves itself with a token:

    token <token>      ->  {"ok": true}  or  {"error": "..."} and the connection closes
    stats              ->  the snapshot

A node's snapshot has ``"node"``, ``"tor"``, ``"traffic"``, ``"connections"``,
``"peers"``, ``"store"`` and ``"warnings"`` (``"v": 1``). A replica answers
``{"v": 1, "kind": "replica", "status": {...}}``, its ``status.json``.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .const import KIND_NODE, KIND_REPLICA

TIMEOUT = 10
LINE_LIMIT = 4 * 1024 * 1024  # a snapshot with many peers and groups
SUPPORTED_VERSION = 1


class UnseenetError(Exception):
    """Something went wrong talking to the stats interface."""


class CannotConnect(UnseenetError):
    """The node or replica could not be reached."""


class InvalidAuth(UnseenetError):
    """The token was refused."""


class UnsupportedVersion(UnseenetError):
    """A snapshot of a version this integration does not know."""


@dataclass
class Snapshot:
    """One answer to ``stats``."""

    kind: str
    data: dict[str, Any]

    @property
    def key(self) -> str | None:
        """The node key or the replica key: stable, so the unique ID."""
        if self.kind == KIND_NODE:
            return self.data.get("node", {}).get("key")
        return self.data.get("status", {}).get("key")

    @property
    def title(self) -> str:
        if self.kind == KIND_NODE:
            return str(self.data.get("node", {}).get("name") or "Unseenet node")
        key = self.key or ""
        short = key.removeprefix("ed25519:")[:8]
        return f"Unseenet replica {short}" if short else "Unseenet replica"


def parse(reply: Any) -> Snapshot:
    """A snapshot from the decoded JSON, or UnseenetError."""
    if not isinstance(reply, dict):
        raise UnseenetError("not a stats snapshot")
    if "error" in reply:
        raise UnseenetError(str(reply["error"]))
    version = reply.get("v")
    if version != SUPPORTED_VERSION:
        raise UnsupportedVersion(
            f"stats version {version!r}; this integration knows version {SUPPORTED_VERSION}"
        )
    if reply.get("kind") == KIND_REPLICA:
        if not isinstance(reply.get("status"), dict):
            raise UnseenetError("a replica snapshot without status")
        return Snapshot(KIND_REPLICA, reply)
    if isinstance(reply.get("node"), dict):
        return Snapshot(KIND_NODE, reply)
    raise UnseenetError("neither a node nor a replica")


class UnseenetClient:
    """Asks one node or replica for its stats."""

    def __init__(self, host: str, port: int, token: str | None) -> None:
        self.host = host
        self.port = port
        self.token = token or None

    async def _ask(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, line: str) -> Any:
        writer.write(line.encode() + b"\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), TIMEOUT)
        if not raw:
            raise CannotConnect("the connection was closed")
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise UnseenetError("the answer is not JSON") from exc

    async def fetch(self) -> Snapshot:
        """The current snapshot."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, limit=LINE_LIMIT), TIMEOUT
            )
        except (TimeoutError, OSError) as exc:
            raise CannotConnect(f"cannot reach {self.host}:{self.port}: {exc}") from exc
        try:
            if self.token:
                answer = await self._ask(reader, writer, f"token {self.token}")
                if not (isinstance(answer, dict) and answer.get("ok")):
                    raise InvalidAuth(
                        str(answer.get("error", "token refused"))
                        if isinstance(answer, dict)
                        else "token refused"
                    )
            return parse(await self._ask(reader, writer, "stats"))
        except (TimeoutError, OSError, asyncio.LimitOverrunError, ValueError) as exc:
            # ValueError: a line longer than LINE_LIMIT
            raise CannotConnect(str(exc) or type(exc).__name__) from exc
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
