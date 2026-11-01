"""A fake stats interface for the tests: speaks the protocol in api.py."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "s3cret-token"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/unseenet in every test."""
    yield


class FakeStats:
    """Answers ``token`` and ``stats`` like a node or a replica would."""

    def __init__(self, snapshot: dict[str, Any], token: str | None = TOKEN) -> None:
        self.snapshot = copy.deepcopy(snapshot)
        self.token = token
        self.server: asyncio.Server | None = None
        self.port = 0
        self.requests: list[str] = []

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        authed = self.token is None
        try:
            while line := await reader.readline():
                parts = line.decode().strip().split()
                self.requests.append(parts[0] if parts else "")
                if parts and parts[0] == "token":
                    if len(parts) == 2 and parts[1] == self.token:
                        authed = True
                        reply: Any = {"ok": True}
                    else:
                        writer.write(b'{"error":"wrong token"}\n')
                        await writer.drain()
                        break
                elif not authed:
                    writer.write(b'{"error":"token first"}\n')
                    await writer.drain()
                    break
                elif parts and parts[0] == "stats":
                    reply = self.snapshot
                else:
                    reply = {"error": "unknown request"}
                writer.write(json.dumps(reply).encode() + b"\n")
                await writer.drain()
        finally:
            writer.close()

    async def start(self) -> FakeStats:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()


@pytest.fixture
async def node_server(socket_enabled):
    server = await FakeStats(load("node")).start()
    yield server
    await server.stop()


@pytest.fixture
async def replica_server(socket_enabled):
    server = await FakeStats(load("replica")).start()
    yield server
    await server.stop()
