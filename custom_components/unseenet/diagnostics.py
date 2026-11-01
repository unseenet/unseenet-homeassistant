"""Diagnostics: the snapshot as the integration last saw it, without the token."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN
from .coordinator import UnseenetConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UnseenetConfigEntry
) -> dict[str, Any]:
    snap = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_TOKEN}),
        "kind": snap.kind,
        "snapshot": snap.data,
    }
