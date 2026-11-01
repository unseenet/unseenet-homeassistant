"""The device every Unseenet entity belongs to."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KIND_NODE
from .coordinator import UnseenetCoordinator


class UnseenetEntity(CoordinatorEntity[UnseenetCoordinator]):
    """One node or replica is one device, named as it names itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UnseenetCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        snap = coordinator.data
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        if snap.kind == KIND_NODE:
            node = snap.data.get("node", {})
            model, version = "Node", node.get("version")
        else:
            model = "Council replica"
            version = str(snap.data["status"].get("software", "")).removeprefix("unseenet-replica ") or None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title,
            manufacturer="Unseenet",
            model=model,
            sw_version=version,
            configuration_url="https://unseenet.org/node/"
            if snap.kind == KIND_NODE
            else "https://unseenet.org/replica/",
        )
