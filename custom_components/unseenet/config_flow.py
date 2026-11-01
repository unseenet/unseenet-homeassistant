"""Set up an Unseenet node or council replica: by hand, or found through the add-on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import CannotConnect, InvalidAuth, Snapshot, UnseenetClient, UnseenetError, UnsupportedVersion
from .const import CONF_KIND, CONF_TOKEN, DEFAULT_PORT, DOMAIN


async def _try(host: str, port: int, token: str | None) -> tuple[Snapshot | None, str | None]:
    """The snapshot, or the key of the error to show."""
    try:
        return await UnseenetClient(host, port, token).fetch(), None
    except CannotConnect:
        return None, "cannot_connect"
    except InvalidAuth:
        return None, "invalid_auth"
    except UnsupportedVersion:
        return None, "unsupported_version"
    except UnseenetError:
        return None, "unknown"


def _schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
        }
    )


class UnseenetConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per node or replica, known by its key."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}
        self._addon = ""

    async def _create(self, snap: Snapshot, data: dict[str, Any]) -> ConfigFlowResult:
        await self.async_set_unique_id(snap.key)
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(title=snap.title, data={**data, CONF_KIND: snap.kind})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST].strip(),
                CONF_PORT: user_input[CONF_PORT],
                CONF_TOKEN: user_input.get(CONF_TOKEN, "").strip(),
            }
            snap, error = await _try(data[CONF_HOST], data[CONF_PORT], data[CONF_TOKEN])
            if snap is not None and not snap.key:
                error = "unknown"
            if error is None:
                return await self._create(snap, data)
            errors["base"] = error
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Found through an Unseenet add-on (its 'discovery: [unseenet]')."""
        config = discovery_info.config
        data = {
            CONF_HOST: str(config[CONF_HOST]),
            CONF_PORT: int(config.get(CONF_PORT, DEFAULT_PORT)),
            CONF_TOKEN: str(config.get(CONF_TOKEN) or ""),
        }
        snap, error = await _try(data[CONF_HOST], data[CONF_PORT], data[CONF_TOKEN])
        if error is not None or snap is None or not snap.key:
            return self.async_abort(reason=error or "unknown")
        await self.async_set_unique_id(snap.key)
        self._abort_if_unique_id_configured(updates=data)
        self._discovered = {**data, CONF_KIND: snap.kind, "title": snap.title}
        self._addon = discovery_info.name
        self.context["title_placeholders"] = {"name": snap.title}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            data = {k: v for k, v in self._discovered.items() if k != "title"}
            return self.async_create_entry(title=self._discovered["title"], data=data)
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._addon, "name": self._discovered["title"]},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The token was refused - most likely the add-on made a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            snap, error = await _try(entry.data[CONF_HOST], entry.data[CONF_PORT], token)
            if error is None and snap is not None:
                await self.async_set_unique_id(snap.key)
                self._abort_if_unique_id_mismatch(reason="wrong_node")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={"name": entry.title},
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Point the entry at a new host, port or token."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST].strip(),
                CONF_PORT: user_input[CONF_PORT],
                CONF_TOKEN: user_input.get(CONF_TOKEN, "").strip(),
            }
            snap, error = await _try(data[CONF_HOST], data[CONF_PORT], data[CONF_TOKEN])
            if error is None and snap is not None:
                await self.async_set_unique_id(snap.key)
                self._abort_if_unique_id_mismatch(reason="wrong_node")
                return self.async_update_reload_and_abort(entry, data_updates=data)
            errors["base"] = error or "unknown"
        return self.async_show_form(
            step_id="reconfigure", errors=errors, data_schema=_schema(user_input or entry.data)
        )
