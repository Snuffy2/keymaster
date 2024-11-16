"""Switch for Keymaster"""

from dataclasses import dataclass
import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady

from .const import CONF_SLOTS, CONF_START, COORDINATOR, DOMAIN
from .entity import KeymasterEntity, KeymasterEntityDescription
from .helpers import async_using_zwave_js

try:
    from homeassistant.components.zwave_js.const import DOMAIN as ZWAVE_JS_DOMAIN
except (ModuleNotFoundError, ImportError):
    pass

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup config entry."""
    coordinator = hass.data[DOMAIN][COORDINATOR]
    kmlock = await coordinator.get_lock_by_config_entry_id(config_entry.entry_id)
    entities = []
    if async_using_zwave_js(hass=hass, kmlock=kmlock):
        lock_switch_entities = {
            "switch.autolock_enabled": "Auto Lock",
            "switch.lock_notifications": "Lock Notifications",
            "switch.door_notifications": "Door Notifications",
            "switch.retry_lock": "Retry Lock",
        }
        for key, name in lock_switch_entities.items():
            entities.append(
                KeymasterSwitch(
                    entity_description=KeymasterSwitchEntityDescription(
                        key=key,
                        name=name,
                        entity_registry_enabled_default=True,
                        hass=hass,
                        config_entry=config_entry,
                        coordinator=coordinator,
                    ),
                )
            )

        for x in range(
            config_entry.data[CONF_START],
            config_entry.data[CONF_START] + config_entry.data[CONF_SLOTS],
        ):
            if kmlock.parent_name:
                entities.append(
                    KeymasterSwitch(
                        entity_description=KeymasterSwitchEntityDescription(
                            key=f"switch.code_slots:{x}.override_parent",
                            name=f"Override Parent",
                            entity_registry_enabled_default=True,
                            hass=hass,
                            config_entry=config_entry,
                            coordinator=coordinator,
                        )
                    )
                )
            code_slot_switch_entities = {
                f"switch.code_slots:{x}.notifications": "Notifications",
                f"switch.code_slots:{x}.accesslimit_date_range_enabled": "Use Date Range Limits",
                f"switch.code_slots:{x}.enabled": "Enabled",
                f"switch.code_slots:{x}.accesslimit_count_enabled": "Limit by Number of Uses",
                f"switch.code_slots:{x}.reset_code_slot": "Reset Code Slot",
                f"switch.code_slots:{x}.accesslimit_day_of_week_enabled": "Use Day of Week Limits",
            }
            for key, name in code_slot_switch_entities.items():
                entities.append(
                    KeymasterSwitch(
                        entity_description=KeymasterSwitchEntityDescription(
                            key=key,
                            name=name,
                            entity_registry_enabled_default=True,
                            hass=hass,
                            config_entry=config_entry,
                            coordinator=coordinator,
                        ),
                    )
                )
            for i, dow in enumerate(
                [
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                ]
            ):
                dow_switch_entities = {
                    f"switch.code_slots:{x}.accesslimit_day_of_week:{i}.dow_enabled": f"{dow}",
                    f"switch.code_slots:{x}.accesslimit_day_of_week:{i}.include_exclude": "Include (On)/Exclude (Off)",
                }
                for key, name in dow_switch_entities.items():
                    entities.append(
                        KeymasterSwitch(
                            entity_description=KeymasterSwitchEntityDescription(
                                key=key,
                                name=name,
                                entity_registry_enabled_default=True,
                                hass=hass,
                                config_entry=config_entry,
                                coordinator=coordinator,
                            ),
                        )
                    )
    else:
        _LOGGER.error("Z-Wave integration not found")
        raise PlatformNotReady

    async_add_entities(entities, True)
    return True


@dataclass(kw_only=True)
class KeymasterSwitchEntityDescription(
    KeymasterEntityDescription, SwitchEntityDescription
):
    pass


class KeymasterSwitch(KeymasterEntity, SwitchEntity):

    def __init__(
        self,
        entity_description: KeymasterSwitchEntityDescription,
    ) -> None:
        """Initialize Switch"""
        super().__init__(
            entity_description=entity_description,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        # _LOGGER.debug(f"[Switch handle_coordinator_update] self.coordinator.data: {self.coordinator.data}")
        if not self._kmlock.connected:
            self._attr_available = False
            self.async_write_ha_state()
            return

        if (
            "code_slots" in self._property
            and not (
                self._property.endswith(".override_parent")
                or self._property.endswith(".notifications")
            )
            and self._kmlock.parent_name is not None
            and not self._kmlock.code_slots[self._code_slot].override_parent
        ):
            self._attr_available = False
            self.async_write_ha_state()
            return

        if (
            not self._property.endswith(".enabled")
            and "code_slots" in self._property
            and (
                self._code_slot not in self._kmlock.code_slots
                or not self._kmlock.code_slots[self._code_slot].enabled
            )
        ):
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        self._attr_is_on = self._get_property_value()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""

        if self.is_on:
            return

        _LOGGER.debug(
            f"[Switch async_turn_on] {self.name}: config_entry_id: {self._config_entry.entry_id}"
        )

        # if (
        #     self._property.endswith(".accesslimit_count")
        #     and self._kmlock.parent_name is not None
        #     and not self._kmlock.code_slots[self._code_slot].override_parent
        # ):
        #     _LOGGER.debug(
        #         f"[Switch async_turn_on] {self._kmlock.lock_name}: Child lock and code slot {self._code_slot} not set to override parent. Ignoring change"
        #     )
        #     return
        if self._set_property_value(True):
            self._attr_is_on = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""

        if not self.is_on:
            return

        _LOGGER.debug(
            f"[Switch async_turn_off] {self.name}: config_entry_id: {self._config_entry.entry_id}"
        )

        # if (
        #     self._property.endswith(".accesslimit_count")
        #     and self._kmlock.parent_name is not None
        #     and not self._kmlock.code_slots[self._code_slot].override_parent
        # ):
        #     _LOGGER.debug(
        #         f"[Switch async_turn_off] {self._kmlock.lock_name}: Child lock and code slot {self._code_slot} not set to override parent. Ignoring change"
        #     )
        #     return
        if self._set_property_value(False):
            self._attr_is_on = False
