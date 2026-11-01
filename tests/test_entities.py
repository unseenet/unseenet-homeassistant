"""Sensors, peers, repair issues and diagnostics."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.unseenet.const import CONF_KIND, CONF_TOKEN, DOMAIN

from .conftest import TOKEN


async def setup(hass: HomeAssistant, server, kind: str, title: str) -> MockConfigEntry:
    key = server.snapshot["node"]["key"] if kind == "node" else server.snapshot["status"]["key"]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=key,
        title=title,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: server.port, CONF_TOKEN: TOKEN, CONF_KIND: kind},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        key.split(":")[0], DOMAIN, f"{entry.unique_id}_{key.split(':')[1]}"
    )
    assert entity_id, key
    return entity_id


async def test_node(hass: HomeAssistant, node_server) -> None:
    entry = await setup(hass, node_server, "node", "ha-unseenet")
    assert entry.state is ConfigEntryState.LOADED

    def state(key: str) -> str:
        return hass.states.get(entity(hass, entry, key)).state

    assert state("sensor:tor") == "running"
    assert state("sensor:accepted_hour") == "60"
    assert state("sensor:rejected_hour") == "2"
    assert state("sensor:groups") == "412"
    assert state("sensor:peers_open") == "3"
    assert state("sensor:contact_new") == "1"
    assert state("sensor:warnings") == "1"
    assert state("binary_sensor:tor_running") == "on"
    assert state("binary_sensor:problem") == "on"
    assert state("binary_sensor:peer_node3") == "on"
    assert state("binary_sensor:peer_friend") == "off"
    friend = hass.states.get(entity(hass, entry, "binary_sensor:peer_friend"))
    assert friend.attributes["last_error"] == "connection refused"

    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_warnings")
    assert issue is not None
    assert "contact inbox" in issue.translation_placeholders["warnings"]

    # a new peer and no warnings at the next poll
    node_server.snapshot["peers"].append(dict(node_server.snapshot["peers"][0], name="node4"))
    node_server.snapshot["warnings"] = []
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("binary_sensor:peer_node4") == "on"
    assert state("binary_sensor:problem") == "off"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_warnings") is None

    # the node goes away: its entities become unavailable
    await node_server.stop()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("sensor:tor") == "unavailable"


async def test_replica(hass: HomeAssistant, replica_server) -> None:
    entry = await setup(hass, replica_server, "replica", "Unseenet replica s3x2dksm")

    def state(key: str) -> str:
        return hass.states.get(entity(hass, entry, key)).state

    assert state("sensor:role") == "shadow"
    assert state("sensor:level") == "2"
    assert state("sensor:members") == "3"
    assert state("binary_sensor:twin") == "off"
    assert state("binary_sensor:waiting_for_you") == "off"

    replica_server.snapshot["status"]["twin"] = {
        "message_id": "<abc@x>",
        "subject": "report 2026-11-01",
        "date": "2026-11-01T19:00:00Z",
    }
    replica_server.snapshot["status"]["held"] = {"removal:ed25519:x": {"kind": "removal"}}
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("binary_sensor:twin") == "on"
    assert state("sensor:held") == "1"
    issues = ir.async_get(hass)
    twin = issues.async_get_issue(DOMAIN, f"{entry.entry_id}_twin")
    assert twin is not None and twin.severity is ir.IssueSeverity.CRITICAL
    assert issues.async_get_issue(DOMAIN, f"{entry.entry_id}_held") is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert issues.async_get_issue(DOMAIN, f"{entry.entry_id}_twin") is None


async def test_wrong_token_starts_reauth(hass: HomeAssistant, node_server) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="k",
        data={CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: "old", CONF_KIND: "node"},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_diagnostics(hass: HomeAssistant, hass_client, node_server) -> None:
    entry = await setup(hass, node_server, "node", "ha-unseenet")
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag["entry"][CONF_TOKEN] == "**REDACTED**"
    assert diag["snapshot"]["node"]["name"] == "ha-unseenet"
