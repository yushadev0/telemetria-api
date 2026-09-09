"""
warm_cache.py  --  f1_cache/ klasorunu DISARIDA (F1'e erisebilen bir makinede) doldur.

Neden: canli sunucunun IP'si (Contabo / AS51167) F1'in CloudFront'u tarafindan
403 ile bloklaniyor -> `session.load()` telemetri/timing indiremiyor. Cozum:
bu betigi bloklanmayan bir makinede calistir, olusan `f1_cache/` klasorunu
sunucuya kopyala. FastF1 sonra %100 diskten okur, F1'i hic aramaz.

Kullanim:
    # duzenle: asagidaki SESSIONS listesi
    python scripts/warm_cache.py
    # ya da komut satirindan tek seans:
    python scripts/warm_cache.py 2024 "Bahrain Grand Prix" Race

Sonra sunucuya:
    rsync -av f1_cache/  kullanici@sunucu:/c/WEBS/yusa.app/telemetria-api/f1_cache/
    # (Windows'ta: klasoru komple kopyala / scp -r)

Not: FastF1 surumu iki tarafta ayni olmali (requirements.txt -> 3.8.1).
Bitmis (gecmis) yarislarin verisi degismez; cache kalicidir.
"""
import os
import sys
import time

# scripts/ altindan calisinca repo kokunu import path'ine ekle.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# services/f1_service import edilince fastf1 cache'i f1_cache/ (mutlak yol) olarak acilir.
from services.f1_service import get_loaded_session

# --- Isitilacak seanslar. Ihtiyacina gore duzenle. -------------------------
# (year, race_name, session_type)  --  race_name /schedule/{y}/races'teki "event_name"
SESSIONS = [
    (2024, "Bahrain Grand Prix", "Race"),
    (2024, "Bahrain Grand Prix", "Qualifying"),
    (2024, "Saudi Arabian Grand Prix", "Race"),
    (2024, "Monaco Grand Prix", "Race"),
    (2024, "Monaco Grand Prix", "Qualifying"),
    (2024, "Italian Grand Prix", "Race"),
    (2023, "Bahrain Grand Prix", "Race"),
    (2023, "Monaco Grand Prix", "Qualifying"),
]
# -------------------------------------------------------------------------


def warm(year, race, session):
    label = f"{year} | {race} | {session}"
    t0 = time.time()
    try:
        # with_telemetry=True -> laps + car/pos data (en pahali indirme, hepsini cache'ler)
        get_loaded_session(year, race, session, with_telemetry=True)
        # with_telemetry=False -> drivers / laps endpoint'lerinin paylastigi hafif load
        get_loaded_session(year, race, session, with_telemetry=False)
        print(f"  OK   {label}  ({time.time() - t0:.0f}s)", flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL {label}  -> {exc!r}", flush=True)
        return False


def main():
    if len(sys.argv) == 4:
        targets = [(int(sys.argv[1]), sys.argv[2], sys.argv[3])]
    else:
        targets = SESSIONS

    print(f"{len(targets)} seans isitiliyor...\n", flush=True)
    ok = 0
    for year, race, session in targets:
        ok += warm(year, race, session)
    print(f"\nBitti: {ok}/{len(targets)} basarili. f1_cache/ klasorunu sunucuya kopyala.")


if __name__ == "__main__":
    main()
