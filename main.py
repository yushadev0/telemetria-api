from fastapi import FastAPI, HTTPException
from services.f1_service import get_fastest_lap_telemetry
from core.redis_client import get_from_cache, set_to_cache
from routers import sessions

app = FastAPI(title="Telemetria API", version="0.1.0")

@app.get("/")
def read_root():
    return {"message": "Telemetria API Sistemine Hoş Geldiniz. Motorlar çalışıyor!"}

@app.get("/api/v1/telemetry/{race_year}/{race_name}/{session_type}/{driver_code}")
def get_telemetry(race_year: int, race_name: str, session_type: str, driver_code: str):
    
    # 1. Benzersiz bir önbellek anahtarı (cache key) oluşturuyoruz. Her seans ve pilot için eşsiz olmalı.
    cache_key = f"telemetry_{race_year}_{race_name}_{session_type}_{driver_code}"
    
    # 2. Önce Redis'e (RAM'e) soruyoruz
    cached_response = get_from_cache(cache_key)
    
    # Eğer veri RAM'de varsa, FastF1 veya Pandas'ı hiç yormadan doğrudan dön! (Süper hızlı kısım)
    if cached_response:
        cached_response["cache"] = "hit"  # <--- EKSİK OLAN SİHİRLİ SATIR BU
        return cached_response
        
    # 3. Veri RAM'de yoksa, ağır işçiliği yapmak üzere servisimizi çağırıyoruz
    telemetry_response = get_fastest_lap_telemetry(race_year, race_name, session_type, driver_code)
    
    # Hata kontrolü
    if isinstance(telemetry_response, dict) and "error_message" in telemetry_response:
        raise HTTPException(status_code=400, detail=telemetry_response["error_message"])
        
    # Başarılı yanıtı oluştur
    final_response = {
        "status": "success",
        "cache": "miss", # İstemciye verinin bu seferlik taze hesaplandığını söylüyoruz
        "driver_code": driver_code,
        "track_name": race_name,
        "data_points": len(telemetry_response["time"]) if "time" in telemetry_response else 0,
        "telemetry_data": telemetry_response
    }
    
    # 4. Yanıtı gelecekteki istekler için Redis'e yaz
    set_to_cache(cache_key, final_response)
 
    
    return final_response

app.include_router(sessions.router, prefix="/api/v1/schedule", tags=["Schedule"])