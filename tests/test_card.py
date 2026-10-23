from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.battery_roi import _async_remove_local_copy
from custom_components.battery_roi.const import DOMAIN


async def test_upgrade_removes_the_local_copy(hass: HomeAssistant) -> None:
    """0.5.1 copied the card into /config/www and added it as a /local resource."""
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    await resources.async_create_item({"res_type": "module", "url": f"/local/{DOMAIN}/battery-roi-card.js?v=0.5.1"})
    await resources.async_create_item({"res_type": "module", "url": "/local/other-card.js"})
    local = Path(hass.config.path("www", DOMAIN))
    local.mkdir(parents=True)
    (local / "battery-roi-card.js").write_text("")

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert not local.exists()
    assert [item["url"] for item in resources.async_items()] == ["/local/other-card.js"]

    # Only once: a folder made after the cleanup is left alone.
    local.mkdir()
    await _async_remove_local_copy(hass)
    assert local.exists()
