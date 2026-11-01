"""Binary sensors: Tor, one per peer, and a replica's alarms."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import KIND_NODE
from .coordinator import UnseenetConfigEntry, UnseenetCoordinator
from .entity import UnseenetEntity


@dataclass(frozen=True, kw_only=True)
class UnseenetBinaryDescription(BinarySensorEntityDescription):
    is_on: Callable[[dict], bool | None]


NODE_BINARY: tuple[UnseenetBinaryDescription, ...] = (
    UnseenetBinaryDescription(
        key="tor_running",
        translation_key="tor_running",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on=lambda d: (
            d.get("tor", {}).get("state") == "running" and d.get("tor", {}).get("bootstrap", 100) >= 100
        ),
    ),
    UnseenetBinaryDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda d: bool(d.get("warnings")),
    ),
)

REPLICA_BINARY: tuple[UnseenetBinaryDescription, ...] = (
    UnseenetBinaryDescription(
        key="twin",
        translation_key="twin",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda s: bool(s.get("twin")),
    ),
    UnseenetBinaryDescription(
        key="disputed",
        translation_key="disputed",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda s: bool(s.get("disputed")),
    ),
    UnseenetBinaryDescription(
        key="waiting_for_you",
        translation_key="waiting_for_you",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda s: bool(s.get("held")),
    ),
)


def peer_ok(peer: dict[str, Any]) -> bool:
    """A peer is fine unless its last error is newer than its last delivery."""
    error_at = peer.get("last_error_at")
    if not peer.get("last_error") or not error_at:
        return True
    sent = peer.get("last_sent") or 0
    pulled = peer.get("last_pull") or 0
    return max(sent, pulled) >= error_at


async def async_setup_entry(
    hass: HomeAssistant, entry: UnseenetConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.data.kind != KIND_NODE:
        async_add_entities(UnseenetBinary(coordinator, d) for d in REPLICA_BINARY)
        return
    async_add_entities(UnseenetBinary(coordinator, d) for d in NODE_BINARY)

    known: set[str] = set()

    @callback
    def add_new_peers() -> None:
        """Peers come and go with the node's settings: add the new ones."""
        peers = [p for p in coordinator.data.data.get("peers") or [] if p.get("name")]
        new = [PeerSensor(coordinator, p["name"]) for p in peers if p["name"] not in known]
        known.update(p["name"] for p in peers)
        if new:
            async_add_entities(new)

    add_new_peers()
    entry.async_on_unload(coordinator.async_add_listener(add_new_peers))


class UnseenetBinary(UnseenetEntity, BinarySensorEntity):
    entity_description: UnseenetBinaryDescription

    def __init__(self, coordinator: UnseenetCoordinator, description: UnseenetBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        snap = self.coordinator.data
        data = snap.data if snap.kind == KIND_NODE else snap.data["status"]
        return self.entity_description.is_on(data)


class PeerSensor(UnseenetEntity, BinarySensorEntity):
    """On when the exchange with a peer works; its last error as an attribute."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "peer"

    def __init__(self, coordinator: UnseenetCoordinator, name: str) -> None:
        super().__init__(coordinator, f"peer_{name}")
        self.peer_name = name
        self._attr_translation_placeholders = {"peer": name}

    def _peer(self) -> dict[str, Any] | None:
        return next(
            (p for p in self.coordinator.data.data.get("peers") or [] if p.get("name") == self.peer_name),
            None,
        )

    @property
    def available(self) -> bool:
        return super().available and self._peer() is not None

    @property
    def is_on(self) -> bool | None:
        peer = self._peer()
        return None if peer is None else peer_ok(peer)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        peer = self._peer()
        if peer is None:
            return None
        return {
            k: peer.get(k)
            for k in (
                "address",
                "queue",
                "sent",
                "pulled",
                "last_error",
                "last_pull_result",
                "authenticated_by",
            )
        }
