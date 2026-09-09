"""
scripts/auto_warm.py -- GitHub Actions runner'inda calisir (CI, Contabo degil -> bloklu degil).

2018'den bu yana biten tum Race/Qualifying seanslarini tarar. Workflow bu betikten
ONCE sunucudaki f1_cache/'i rsync ile buraya indirir, betik FastF1'in kendi disk
cache'ine guvenerek zaten var olanlari atlar (network'e gitmez, saniyeler icinde
gecer), sadece eksik olanlari gercekten indirir. Sonra workflow guncellenmis
f1_cache/'i sunucuya geri rsync eder.

Neden burada: sunucunun IP'si (Contabo/AS51167) F1'in CloudFront WAF'i tarafindan
403 ile bloklaniyor; GitHub Actions runner'lari bloklu degil.

Env:
  MAX_NEW_SESSIONS  -- bu calistirmada GERCEKTEN indirilecek (cache'te olmayan)
                       seans sayisi ustsiniri. Ilk calistirmada yillarca birikmis
                       eksik seans olabilir; bunlari tek seferde degil birkac
                       haftalik calistirmaya yayarak indirmek icin. Varsayilan 25.
  TARGET_YEAR, TARGET_RACE, TARGET_SESSION
                    -- ucu de doluysa tam taramayi atlayip SADECE bu tek seansi
                       isitir. Sunucu (services/gh_dispatch.py) cache'te olmayan
                       bir seans istegiyle karsilastiginda workflow_dispatch API'siyle
                       bunlari doldurup workflow'u tetikler.
"""
import os
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fastf1  # noqa: E402
from services.f1_service import get_loaded_session  # noqa: E402

SESSION_TYPES = ["Qualifying", "Race"]
START_YEAR = 2018
MAX_NEW = int(os.getenv("MAX_NEW_SESSIONS", "25"))
# get_loaded_session bir seans icin 2 kez cagriliyor (telemetry True/False).
# Ikisi de disk cache'inden geliyorsa toplam sure tipik olarak <3s; network'e
# gidiyorsa (gercek indirme) bunun kat kat uzerinde surer. Kesin degil ama
# sadece ilerleme sayaci/loglama icin kullaniliyor, MAX_NEW sinirini asmamak
# amacli bir yaklastirma -- yanlis siniflandirma sonucu degistirmez.
CACHE_HIT_THRESHOLD_S = 3.0


def list_targets():
    today = date.today()
    targets = []
    for year in range(START_YEAR, today.year + 1):
        try:
            schedule = fastf1.get_event_schedule(year)
        except Exception as exc:  # noqa: BLE001
            print(f"[SKIP] {year} takvim alinamadi: {exc!r}", flush=True)
            continue
        official = schedule[schedule["EventFormat"] != "testing"]
        for _, row in official.iterrows():
            event_date = row["EventDate"]
            event_date = event_date.date() if hasattr(event_date, "date") else event_date
            if event_date >= today - timedelta(days=1):
                continue  # henuz kosulmamis / veri arsivlenmemis olabilir
            for session_type in SESSION_TYPES:
                targets.append((year, row["EventName"], session_type))
    return targets


def warm(year, event_name, session_type):
    t0 = time.time()
    try:
        get_loaded_session(year, event_name, session_type, with_telemetry=True)
        get_loaded_session(year, event_name, session_type, with_telemetry=False)
        elapsed = time.time() - t0
        return True, elapsed < CACHE_HIT_THRESHOLD_S, elapsed, None
    except Exception as exc:  # noqa: BLE001
        return False, False, time.time() - t0, exc


def _single_target():
    year = os.getenv("TARGET_YEAR", "").strip()
    race = os.getenv("TARGET_RACE", "").strip()
    session = os.getenv("TARGET_SESSION", "").strip()
    if year and race and session:
        return int(year), race, session
    return None


def main():
    single = _single_target()
    if single:
        year, race, session = single
        print(f"Tekli hedef modu: {year} {race} {session}\n", flush=True)
        success, was_cached, elapsed, exc = warm(year, race, session)
        label = f"{year} {race} {session}"
        if not success:
            print(f"  FAIL  {label}  ({elapsed:.0f}s)  -> {exc!r}", flush=True)
            sys.exit(1)
        tag = "zaten cache'teydi" if was_cached else "yeni indirildi"
        print(f"  OK    {label}  ({elapsed:.0f}s)  -- {tag}", flush=True)
        return

    targets = list_targets()
    print(f"{len(targets)} aday seans ({START_YEAR}-{date.today().year}, Race+Qualifying).\n", flush=True)

    new_count = 0
    ok = hit = fail = 0
    for year, event_name, session_type in targets:
        if new_count >= MAX_NEW:
            print(f"\nMAX_NEW_SESSIONS ({MAX_NEW}) sinirina ulasildi; kalanlar bir sonraki calistirmada.", flush=True)
            break

        success, was_cached, elapsed, exc = warm(year, event_name, session_type)
        label = f"{year} {event_name} {session_type}"

        if not success:
            if "RateLimitExceeded" in type(exc).__name__:
                print(f"\nAPI saatlik kotasina ({exc}) carpildi; kalanlar bir sonraki calistirmada denenecek.", flush=True)
                break
            fail += 1
            print(f"  FAIL  {label}  ({elapsed:.0f}s)  -> {exc!r}", flush=True)
            continue

        if was_cached:
            hit += 1
        else:
            ok += 1
            new_count += 1
            print(f"  YENI  {label}  ({elapsed:.0f}s)", flush=True)

    print(f"\nBitti: {ok} yeni indirildi, {hit} zaten cache'teydi, {fail} basarisiz. Toplam aday: {len(targets)}.", flush=True)


if __name__ == "__main__":
    main()
