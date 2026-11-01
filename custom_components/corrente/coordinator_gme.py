"""Keeps the Italian wholesale prices (PUN Index GME or a zone) for today and tomorrow."""

from __future__ import annotations

import logging
import zlib
from datetime import datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core.gme import GmeError, async_fetch_gme, parse_gme_zip
from .core.italy import ITALY_TZ
from .core.schedule import Segment

_LOGGER = logging.getLogger(__name__)

# GME publishes tomorrow's prices in the early afternoon. Each installation asks
# at its own minute after 13:30 so that not everyone calls at once.
_PUBLICATION = time(13, 30)
_CHECK_EVERY = timedelta(minutes=30)
_RETRY_AFTER = timedelta(minutes=30)


def gme_store(hass: HomeAssistant, entry_id: str) -> Store[list]:
    """The last GME prices downloaded for an entry, kept for a restart while GME is down."""
    return Store(hass, 1, f"{DOMAIN}.gme.{entry_id}")


class GmePriceCoordinator(DataUpdateCoordinator[list[Segment]]):
    """Downloads GME prices about once a day: today's, then tomorrow's when published."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, zone: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_gme",
            update_interval=_CHECK_EVERY,
        )
        self.zone = zone
        # A stable minute per installation, 0-59, from the entry id.
        self._minute = zlib.crc32(entry.entry_id.encode()) % 60
        self._last_attempt: datetime | None = None
        self._store = gme_store(hass, entry.entry_id)

    def _covers(self, segments: list[Segment], moment: datetime) -> bool:
        return any(s.start <= moment < s.end for s in segments)

    def _tomorrow_due(self, now: datetime) -> bool:
        local = now.astimezone(ITALY_TZ)
        due = datetime.combine(local.date(), _PUBLICATION, ITALY_TZ) + timedelta(
            minutes=self._minute
        )
        return local >= due

    async def _async_update_data(self) -> list[Segment]:
        now = dt_util.utcnow()
        local = now.astimezone(ITALY_TZ)
        today = local.date()
        tomorrow = today + timedelta(days=1)
        tomorrow_noon = datetime.combine(tomorrow, time(12, 0), ITALY_TZ)
        current = [s for s in (self.data or []) if s.end > now]

        need_today = not self._covers(current, now)
        need_tomorrow = self._tomorrow_due(now) and not self._covers(current, tomorrow_noon)
        if not need_today and not need_tomorrow:
            return current
        if (
            not need_today
            and self._last_attempt is not None
            and now - self._last_attempt < _RETRY_AFTER
        ):
            return current

        self._last_attempt = now
        try:
            raw = await async_fetch_gme(async_get_clientsession(self.hass), today, tomorrow)
            segments = parse_gme_zip(raw, self.zone)
        except GmeError as err:
            if need_today:
                # After a restart while GME is down: the prices saved last time, if they
                # still cover now (GME publishes today's and tomorrow's the day before).
                saved = [s for s in await self._async_saved() if s.end > now]
                if self._covers(saved, now):
                    _LOGGER.warning("GME not reachable, using the prices saved before: %s", err)
                    return saved
                raise UpdateFailed(f"GME prices not available: {err}") from err
            _LOGGER.debug("Tomorrow's GME prices not available yet: %s", err)
            return current
        fresh = [s for s in segments if s.end > now]
        if not self._covers(fresh, now):
            raise UpdateFailed("GME has no price for the current quarter hour")
        await self._store.async_save(
            [
                {"start": s.start.isoformat(), "end": s.end.isoformat(), "price": s.price}
                for s in fresh
            ]
        )
        return fresh

    async def _async_saved(self) -> list[Segment]:
        saved = await self._store.async_load() or []
        return [
            Segment(
                datetime.fromisoformat(s["start"]), datetime.fromisoformat(s["end"]), s["price"]
            )
            for s in saved
        ]
