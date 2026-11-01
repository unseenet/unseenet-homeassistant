"""The Unseenet integration: status of an Unseenet node or council replica.

Reads the stats interface of a node or replica - typically the Unseenet add-ons
beside Home Assistant (unseenet/unseenet-haos-addons) - and shows it as sensors,
binary sensors and repair issues. It changes nothing on the node.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .api import UnseenetClient
from .const import CONF_TOKEN, DOMAIN
from .coordinator import UnseenetConfigEntry, UnseenetCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: UnseenetConfigEntry) -> bool:
    client = UnseenetClient(entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data.get(CONF_TOKEN))
    coordinator = UnseenetCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnseenetConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: UnseenetConfigEntry) -> None:
    """Take the entry's repair issues away with it."""
    for what in ("warnings", "twin", "held"):
        ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_{what}")
