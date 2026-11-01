"""Sensors of a node (traffic, store, Tor) and of a council replica (role, council)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import KIND_NODE
from .coordinator import UnseenetConfigEntry, UnseenetCoordinator
from .entity import UnseenetEntity

TOR_STATES = ["running", "off", "down"]
ROLES = ["waiting", "shadow", "member_on_probation", "full_member"]


def _last_hour(series: str) -> Callable[[dict], Any]:
    return lambda d: sum((d.get("traffic", {}).get("per_minute", {}).get(series) or [])[-60:])


def _total_accepted(d: dict) -> int:
    return sum((d.get("traffic", {}).get("accepted") or {}).values())


def _started(d: dict) -> datetime | None:
    uptime = d.get("node", {}).get("uptime")
    if not isinstance(uptime, (int, float)):
        return None
    # rounded to the minute, so the state does not change at every poll
    return (dt_util.utcnow() - timedelta(seconds=uptime)).replace(second=0, microsecond=0)


def _time(value: Any) -> datetime | None:
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


@dataclass(frozen=True, kw_only=True)
class UnseenetSensorDescription(SensorEntityDescription):
    """``value`` reads the snapshot (a node's, or a replica's status)."""

    value: Callable[[dict], Any]


NODE_SENSORS: tuple[UnseenetSensorDescription, ...] = (
    UnseenetSensorDescription(
        key="tor",
        translation_key="tor",
        device_class=SensorDeviceClass.ENUM,
        options=TOR_STATES,
        value=lambda d: d.get("tor", {}).get("state"),
    ),
    UnseenetSensorDescription(
        key="tor_bootstrap",
        translation_key="tor_bootstrap",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.get("tor", {}).get("bootstrap"),
    ),
    UnseenetSensorDescription(
        key="accepted_hour",
        translation_key="accepted_hour",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.MEASUREMENT,
        value=_last_hour("accepted"),
    ),
    UnseenetSensorDescription(
        key="sent_hour",
        translation_key="sent_hour",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.MEASUREMENT,
        value=_last_hour("sent"),
    ),
    UnseenetSensorDescription(
        key="served_hour",
        translation_key="served_hour",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.MEASUREMENT,
        value=_last_hour("served"),
    ),
    UnseenetSensorDescription(
        key="rejected_hour",
        translation_key="rejected_hour",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.MEASUREMENT,
        value=_last_hour("rejected"),
    ),
    UnseenetSensorDescription(
        key="accepted_total",
        translation_key="accepted_total",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value=_total_accepted,
    ),
    UnseenetSensorDescription(
        key="connections",
        translation_key="connections",
        native_unit_of_measurement="connections",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("connections", {}).get("open"),
    ),
    UnseenetSensorDescription(
        key="peers_open",
        translation_key="peers_open",
        native_unit_of_measurement="peers",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("connections", {}).get("peers_open"),
    ),
    UnseenetSensorDescription(
        key="refused",
        translation_key="refused",
        native_unit_of_measurement="connections",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.get("connections", {}).get("refused"),
    ),
    UnseenetSensorDescription(
        key="groups",
        translation_key="groups",
        native_unit_of_measurement="groups",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("store", {}).get("groups"),
    ),
    UnseenetSensorDescription(
        key="articles",
        translation_key="articles",
        native_unit_of_measurement="posts",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("store", {}).get("articles"),
    ),
    UnseenetSensorDescription(
        key="stored",
        translation_key="stored",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: d.get("store", {}).get("bytes"),
    ),
    UnseenetSensorDescription(
        key="disk_free",
        translation_key="disk_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.get("store", {}).get("disk_free"),
    ),
    UnseenetSensorDescription(
        key="contact_new",
        translation_key="contact_new",
        native_unit_of_measurement="messages",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: (d.get("contact") or {}).get("new", 0),
    ),
    UnseenetSensorDescription(
        key="warnings",
        translation_key="warnings",
        native_unit_of_measurement="warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda d: len(d.get("warnings") or []),
    ),
    UnseenetSensorDescription(
        key="started",
        translation_key="started",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_started,
    ),
)

REPLICA_SENSORS: tuple[UnseenetSensorDescription, ...] = (
    UnseenetSensorDescription(
        key="role",
        translation_key="role",
        device_class=SensorDeviceClass.ENUM,
        options=ROLES,
        value=lambda s: (s.get("role") or "").replace(" ", "_") or None,
    ),
    UnseenetSensorDescription(
        key="level",
        translation_key="level",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.get("level"),
    ),
    UnseenetSensorDescription(
        key="members",
        translation_key="members",
        native_unit_of_measurement="members",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.get("members"),
    ),
    UnseenetSensorDescription(
        key="full_members",
        translation_key="full_members",
        native_unit_of_measurement="members",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.get("full"),
    ),
    UnseenetSensorDescription(
        key="held",
        translation_key="held",
        native_unit_of_measurement="changes",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: len(s.get("held") or {}),
    ),
    UnseenetSensorDescription(
        key="reports_60",
        translation_key="reports_60",
        native_unit_of_measurement="days",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.get("reports_60"),
    ),
    UnseenetSensorDescription(
        key="agreeing_60",
        translation_key="agreeing_60",
        native_unit_of_measurement="days",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s: s.get("agreeing_60"),
    ),
    UnseenetSensorDescription(
        key="decisions",
        translation_key="decisions",
        native_unit_of_measurement="decisions",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.get("decisions"),
    ),
    UnseenetSensorDescription(
        key="full_from",
        translation_key="full_from",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda s: _time(s.get("full_from")),
    ),
    UnseenetSensorDescription(
        key="last_round",
        translation_key="last_round",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: _time(s.get("time")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: UnseenetConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    node = coordinator.data.kind == KIND_NODE
    async_add_entities(UnseenetSensor(coordinator, d) for d in (NODE_SENSORS if node else REPLICA_SENSORS))


class UnseenetSensor(UnseenetEntity, SensorEntity):
    entity_description: UnseenetSensorDescription

    def __init__(self, coordinator: UnseenetCoordinator, description: UnseenetSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        snap = self.coordinator.data
        data = snap.data if snap.kind == KIND_NODE else snap.data["status"]
        return self.entity_description.value(data)
