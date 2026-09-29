from pathlib import Path

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.battery_roi.config_flow import _nest
from custom_components.battery_roi.const import DOMAIN, VERSION

from .test_integration import INPUT


async def test_card_is_a_dashboard_resource_served_from_local(hass: HomeAssistant) -> None:
    """Dashboards opened while Home Assistant starts must still find the card."""
    assert await async_setup_component(hass, "lovelace", {})
    hass.states.async_set("sensor.ecoflow_power", "0", {"unit_of_measurement": "W"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    await hass.config_entries.flow.async_configure(result["flow_id"], _nest(INPUT))
    await hass.async_block_till_done()

    local = Path(hass.config.path("www", DOMAIN))
    assert (local / "battery-roi-card.js").read_text().find(f'CARD_VERSION = "{VERSION}"') > 0
    assert (local / "lit.js").exists()
    resources = hass.data["lovelace"].resources
    urls = [item["url"] for item in resources.async_items()]
    assert urls == [f"/local/{DOMAIN}/battery-roi-card.js?v={VERSION}"]

    # Removing the integration cleans up after itself.
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not local.exists()
    assert list(resources.async_items()) == []
