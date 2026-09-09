"""
services/gh_dispatch.py -- sunucu, F1 CDN blogu yuzunden cache'te olmayan bir
seansla karsilastiginda GitHub Actions'taki f1-cache-warm workflow'unu
workflow_dispatch API'siyle tetikler; workflow o TEK seansi CI runner'inda
indirip (bloklu degil) rsync ile buraya geri gonderir.

Gereken ortam degiskeni: GITHUB_DISPATCH_TOKEN -- repo'ya sadece
"Actions: Read and write" izni olan bir fine-grained GitHub PAT. Verilmezse
bu modul sessizce devre disi kalir, davranis degismez (eski hata mesaji doner).
"""
import logging
import os

import requests

from core.redis_client import redis_db_client

_log = logging.getLogger("gh_dispatch")

_TOKEN = os.getenv("GITHUB_DISPATCH_TOKEN", "").strip()
_REPO = os.getenv("GITHUB_DISPATCH_REPO", "yushadev0/telemetria-api").strip()
_WORKFLOW = os.getenv("GITHUB_DISPATCH_WORKFLOW", "f1-cache-warm.yml").strip()
_REF = os.getenv("GITHUB_DISPATCH_REF", "main").strip()
# Ayni (year, race, session) icin tekrar tekrar tetiklememek adina kilit suresi.
# Bircok kullanici ayni bloklu seansi ust uste isteyebilir; workflow zaten
# birkac dakika suruyor, bu sure boyunca yeni tetikleme atlanir.
_DEBOUNCE_SECONDS = int(os.getenv("GITHUB_DISPATCH_DEBOUNCE", "900"))


def trigger_cache_warm(race_year, race_name: str, session_type: str) -> bool:
    """
    True: workflow bu istekle ya da yakin zamandaki bir onceki istekle tetiklendi
          (yani veri birazdan hazir olacak -- cagiran taraf kullaniciya "bekle" diyebilir).
    False: tetiklenemedi (token yok ya da GitHub API hatasi) -- eski davranisa don.
    """
    if not _TOKEN:
        return False

    lock_key = f"gh_dispatch_lock:{race_year}:{race_name}:{session_type}".lower()
    try:
        is_new = redis_db_client.set(lock_key, "1", nx=True, ex=_DEBOUNCE_SECONDS)
    except Exception as exc:  # noqa: BLE001 - Redis coksede tetiklemeyi engelleme
        _log.error("Debounce kontrolu basarisiz, yine de tetikleniyor: %r", exc)
        is_new = True

    if not is_new:
        return True  # az once tetiklenmis, workflow zaten calisiyor olmali

    url = f"https://api.github.com/repos/{_REPO}/actions/workflows/{_WORKFLOW}/dispatches"
    payload = {
        "ref": _REF,
        "inputs": {
            "target_year": str(race_year),
            "target_race": race_name,
            "target_session": session_type,
        },
    }
    headers = {
        "Authorization": f"Bearer {_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 204:
            _log.error("GitHub dispatch basarisiz (%s): %s", resp.status_code, resp.text[:300])
            return False
        _log.warning("GitHub Actions cache-warm tetiklendi: %s %s %s", race_year, race_name, session_type)
        return True
    except Exception as exc:  # noqa: BLE001
        _log.error("GitHub dispatch istegi atilamadi: %r", exc)
        return False
