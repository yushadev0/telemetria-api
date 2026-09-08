import redis
import os
import json

# Docker-compose'dan gelen REDIS_HOST bilgisini al, bulamazsa localhost kullan
redis_host = os.getenv("REDIS_HOST", "localhost")

# Değişkenimizi snake_case formatında tanımladık
redis_db_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

def get_from_cache(cache_key: str):
    """Veriyi Redis RAM'inden okur ve dict'e parse eder."""
    try:
        # Burada redis_db_client kullanıyoruz
        cached_data = redis_db_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        return None
    except Exception as error_message:
        print(f"Redis Okuma Hatası: {error_message}")
        return None

def get_raw_from_cache(cache_key: str):
    """
    Veriyi Redis'ten HAM JSON string olarak okur (json.loads YOK).
    Cache-hit yolunda parse + yeniden serialize maliyetini tamamen atlamak icin;
    donen string dogrudan Response govdesi olarak kullanilir.
    """
    try:
        return redis_db_client.get(cache_key)  # decode_responses=True -> str | None
    except Exception as error_message:
        print(f"Redis Okuma Hatası: {error_message}")
        return None

def set_to_cache(cache_key: str, data: dict, expire_time: int = 86400):
    """Veriyi Redis'e yazar (bosluksuz/compact JSON)."""
    try:
        # separators=(",", ":") -> gereksiz bosluk yok; hem Redis bellegi hem de
        # cache-hit yolunda tel'e giden govde ~%10-15 kucuk (gzip oncesi).
        # ensure_ascii varsayilan (True): govde saf ASCII kalir, charset belirsizligi olmaz.
        json_data = json.dumps(data, separators=(",", ":"))
        redis_db_client.setex(cache_key, expire_time, json_data)
    except Exception as error_message:
        print(f"Redis Yazma Hatası: {error_message}")