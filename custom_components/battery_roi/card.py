"""Make sure every dashboard can find the card, even while Home Assistant starts.

The card is loaded on every page from this integration's own URL. That URL
only exists once the integration is set up, which on a busy system can be a
minute or more after the dashboard is already reachable. A page opened in that
window never loads the card and shows "Configuration error" until it is
reloaded. So a copy of the card also goes into /config/www, which Home
Assistant serves from the very start, and is added as a dashboard resource.
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

SOURCE = Path(__file__).parent / "frontend"
CARD_FILE = "battery-roi-card.js"
LOCAL_URL = f"/local/{DOMAIN}/{CARD_FILE}"


async def async_install(hass: HomeAssistant) -> None:
    await hass.async_add_executor_job(_copy, Path(hass.config.path("www", DOMAIN)))
    if (resources := await _resources(hass)) is None:
        return
    url = f"{LOCAL_URL}?v={VERSION}"
    for item in resources.async_items():
        if item["url"].split("?")[0] == LOCAL_URL:
            if item["url"] != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return
    await resources.async_create_item({"res_type": "module", "url": url})


async def async_uninstall(hass: HomeAssistant) -> None:
    if (resources := await _resources(hass)) is not None:
        for item in list(resources.async_items()):
            if item["url"].split("?")[0] == LOCAL_URL:
                await resources.async_delete_item(item["id"])
    await hass.async_add_executor_job(
        shutil.rmtree, hass.config.path("www", DOMAIN), True
    )


async def _resources(hass: HomeAssistant):
    """The dashboard resources, or None when they are managed in YAML."""
    lovelace = hass.data.get("lovelace")
    resources = lovelace.get("resources") if isinstance(lovelace, dict) else getattr(lovelace, "resources", None)
    if not hasattr(resources, "async_create_item"):
        return None
    await resources.async_get_info()  # loads the stored resources
    return resources


def _copy(target: Path) -> None:
    # /local only exists when www existed at startup, so a new folder only
    # takes effect after the next restart; until then the normal URL covers it.
    target.mkdir(parents=True, exist_ok=True)
    for source in SOURCE.glob("*.js"):
        if not (target / source.name).exists() or not filecmp.cmp(source, target / source.name, shallow=False):
            shutil.copyfile(source, target / source.name)
