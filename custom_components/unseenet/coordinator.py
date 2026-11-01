"""Polls one node or council replica and keeps its repair issues up to date."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import InvalidAuth, Snapshot, UnseenetClient, UnseenetError
from .const import DOMAIN, KIND_NODE, SCAN_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)

type UnseenetConfigEntry = ConfigEntry[UnseenetCoordinator]


class UnseenetCoordinator(DataUpdateCoordinator[Snapshot]):
    """Fetches the stats snapshot every half minute."""

    config_entry: UnseenetConfigEntry

    def __init__(self, hass: HomeAssistant, entry: UnseenetConfigEntry, client: UnseenetClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> Snapshot:
        try:
            snap = await self.client.fetch()
        except InvalidAuth as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except UnseenetError as exc:
            raise UpdateFailed(str(exc)) from exc
        self._issues(snap)
        return snap

    def issue_id(self, what: str) -> str:
        return f"{self.config_entry.entry_id}_{what}"

    def _issues(self, snap: Snapshot) -> None:
        """The node's warnings and a replica's twin alarm as repair issues."""
        name = self.config_entry.title
        if snap.kind == KIND_NODE:
            warnings = [str(w) for w in snap.data.get("warnings") or []]
            if warnings:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self.issue_id("warnings"),
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="node_warnings",
                    translation_placeholders={
                        "name": name,
                        "warnings": "\n".join(f"- {w}" for w in warnings),
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, self.issue_id("warnings"))
            return
        status = snap.data["status"]
        twin = status.get("twin")
        if twin:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self.issue_id("twin"),
                is_fixable=False,
                severity=ir.IssueSeverity.CRITICAL,
                translation_key="replica_twin",
                translation_placeholders={
                    "name": name,
                    "subject": str(twin.get("subject", "")),
                    "message_id": str(twin.get("message_id", "")),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id("twin"))
        held = status.get("held") or {}
        if held:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self.issue_id("held"),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="replica_held",
                translation_placeholders={"name": name, "changes": "\n".join(f"- {label}" for label in held)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id("held"))

    def clear_issues(self) -> None:
        for what in ("warnings", "twin", "held"):
            ir.async_delete_issue(self.hass, DOMAIN, self.issue_id(what))
