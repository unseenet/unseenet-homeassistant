"""Setting an entry up: by hand, through the add-on, and with a new token."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unseenet.const import CONF_KIND, CONF_TOKEN, DOMAIN

from .conftest import TOKEN

NODE_KEY = "ed25519:bjhcf6tbf2yt37vn7iomsdg5o4xlvdvudjndnm4prrveiur3cukq"


async def test_user(hass: HomeAssistant, node_server) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ha-unseenet"
    assert result["data"][CONF_KIND] == "node"
    assert result["result"].unique_id == NODE_KEY


async def test_user_errors(hass: HomeAssistant, node_server) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: "x"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: 9, CONF_TOKEN: TOKEN}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_already_configured(hass: HomeAssistant, node_server) -> None:
    MockConfigEntry(
        domain=DOMAIN, unique_id=NODE_KEY, data={CONF_HOST: "old", CONF_PORT: 1120, CONF_TOKEN: "old"}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: TOKEN}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hassio(hass: HomeAssistant, node_server) -> None:
    info = HassioServiceInfo(
        config={CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: TOKEN},
        name="Unseenet node",
        slug="a0d7b954_unseenet_node",
        uuid="1234",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=info
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == TOKEN


async def test_hassio_updates_a_known_node(hass: HomeAssistant, node_server) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=NODE_KEY,
        data={CONF_HOST: "old", CONF_PORT: 1120, CONF_TOKEN: "old", CONF_KIND: "node"},
    )
    entry.add_to_hass(hass)
    info = HassioServiceInfo(
        config={CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: TOKEN},
        name="Unseenet node",
        slug="a0d7b954_unseenet_node",
        uuid="1234",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=info
    )
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_TOKEN] == TOKEN


async def test_reauth(hass: HomeAssistant, node_server) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=NODE_KEY,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: node_server.port, CONF_TOKEN: "old", CONF_KIND: "node"},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "x"})
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == TOKEN
