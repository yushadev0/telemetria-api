"""
B5 - Startup pre-warm.

Sunucu acilinca arka planda (event loop'u bloklamadan) EN SON BITMIS yarisin
populer seans/pilot telemetrisini onceden hesaplayip Redis'e yazar. Boylece ilk
kullanici istegi 'cache HIT' olur, 15-40 sn'lik FastF1 yuklemesini yemez.

Hepsi best-effort: hata olursa sadece log'a duser, API'yi etkilemez.
Env ile ayarlanir:
  PREWARM=0             -> tamamen kapat
  PREWARM_DELAY=12      -> startup'tan kac sn sonra basla
  PREWARM_SESSIONS=Q,R  -> hangi seanslar
  PREWARM_DRIVERS=VER,LEC,HAM,NOR,PIA,RUS
"""
import os
import time
import asyncio
import traceback
from datetime import date

import fastf1

from core.redis_client import get_raw_from_cache, set_to_cache
from core import cache_keys as ck
from services.f1_service import get_lap_telemetry, get_driver_laps_summary

PREWARM_ENABLED = os.getenv("PREWARM", "1") == "1"
PREWARM_DELAY = int(os.getenv("PREWARM_DELAY", "12"))
PREWARM_SESSIONS = [s.strip() for s in os.getenv("PREWARM_SESSIONS", "Q,R").split(",") if s.strip()]
PREWARM_DRIVERS = [d.strip() for d in os.getenv("PREWARM_DRIVERS", "VER,LEC,HAM,NOR,PIA,RUS").split(",") if d.strip()]


def _most_recent_completed_event(year):
    try:
        sched = fastf1.get_event_schedule(year, include_testing=False)
    except Exception:
        traceback.print_exc()
        return None
    past = sched[sched["EventDate"].dt.date < date.today()]
    if past.empty:
        return None
    return past.iloc[-1]


def _warm_laps(year, race_name, session_type, driver):
    key = ck.laps_summary(year, race_name, session_type, driver)
    if get_raw_from_cache(key):
        return
    r = get_driver_laps_summary(year, race_name, session_type, driver)
    if not (isinstance(r, dict) and "error_message" not in r and r.get("laps")):
        return
    set_to_cache(key, {
        "status": "success", "cache": "miss", "driver_code": driver,
        "track_name": race_name, "session_type": session_type,
        "total_laps": len(r["laps"]), "laps_data": r["laps"],
    })


def _warm_telemetry(year, race_name, session_type, driver):
    key = ck.telemetry(year, race_name, session_type, driver, "fastest")
    if get_raw_from_cache(key):
        return
    r = get_lap_telemetry(year, race_name, session_type, driver, "fastest")
    if not (isinstance(r, dict) and "error_message" not in r):
        return
    set_to_cache(key, {
        "status": "success", "cache": "miss", "driver_code": driver,
        "track_name": race_name, "lap_requested": "fastest",
        "data_points": len(r.get("time", [])), "telemetry_data": r,
    })


def _prewarm_blocking():
    year = date.today().year
    event = _most_recent_completed_event(year)
    if event is None and year > 2018:
        year -= 1
        event = _most_recent_completed_event(year)
    if event is None:
        print("[PREWARM] Uygun bitmis yaris bulunamadi, atlaniyor.", flush=True)
        return

    race_name = str(event["EventName"])
    print(f"[PREWARM] {year} - {race_name} | seanslar={PREWARM_SESSIONS} pilotlar={PREWARM_DRIVERS}", flush=True)

    for session_type in PREWARM_SESSIONS:
        for driver in PREWARM_DRIVERS:
            for fn in (_warm_laps, _warm_telemetry):
                try:
                    fn(year, race_name, session_type, driver)
                except Exception:
                    traceback.print_exc()
                time.sleep(0.5)  # gercek isteklere nefes payi birak
        print(f"[PREWARM] {session_type} tamam.", flush=True)

    print("[PREWARM] Bitti.", flush=True)


async def run_prewarm():
    if not PREWARM_ENABLED:
        print("[PREWARM] Kapali (PREWARM=0).", flush=True)
        return
    await asyncio.sleep(PREWARM_DELAY)
    try:
        # Bloklayan FastF1 isini thread'e at; event loop / UDP / websocket etkilenmesin.
        await asyncio.to_thread(_prewarm_blocking)
    except Exception:
        traceback.print_exc()
