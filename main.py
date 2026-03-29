import asyncio
import socket
import json
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from services.f1_service import get_lap_telemetry, get_comparison_telemetry, get_driver_laps_summary
from core.redis_client import get_from_cache, set_to_cache
from routers import sessions
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import time
import traceback

# Rate Limiter'ı IP adresine göre başlatıyoruz
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Telemetria API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Tarayıcı (Frontend) izinleri (Canlı WebSocket bağlantısı için gerekli)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================================================================
# BÖLÜM 1: ASSETTO CORSA CANLI PİT DUVARI (MULTI-ROOM MİMARİSİ)
# ====================================================================

# Artık tek bir liste değil, Oda Kodlarına göre ayrılmış Sözlük (Dictionary) kullanıyoruz
# Örnek: { "HAMILTON44": [websocket1, websocket2], "VERSTAPPEN33": [websocket3] }
active_rooms = {}
active_streams = {} 

UDP_IP = "0.0.0.0"
UDP_PORT = 4433
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)

async def udp_listener():
    print(f"[BASARILI] Assetto Corsa UDP Koprusu {UDP_PORT} portunda coklu oda destegiyle acildi!")
    loop = asyncio.get_event_loop()
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            telemetry_str = data.decode('utf-8')
            
            telemetry_data = json.loads(telemetry_str)
            room_id = telemetry_data.get("room")
            
            if room_id:
                # 🧠 YENİ: Odanın canlı olduğunu ve son veri gelme zamanını kaydet!
                active_streams[room_id] = time.time()
                
                if room_id in active_rooms:
                    dead_connections = []
                    for connection in active_rooms[room_id]:
                        try:
                            await connection.send_text(telemetry_str)
                        except Exception:
                            dead_connections.append(connection)
                    
                    for c in dead_connections:
                        if c in active_rooms[room_id]:
                            active_rooms[room_id].remove(c)
                        
        except BlockingIOError:
            await asyncio.sleep(0.01)
        except json.JSONDecodeError:
            pass 
        except Exception as e:
            await asyncio.sleep(0.01)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(udp_listener())

# DİKKAT: Uç noktamıza {room_id} değişkeni eklendi!
@app.websocket("/ws/live/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    # YENİ: flush=True ile NSSM'in logları anında diske yazmasını zorluyoruz!
    print(f"[WS]  ODA {room_id}: Istemci baglandi!", flush=True)
    
    if room_id not in active_rooms:
        active_rooms[room_id] = []
        
    active_rooms[room_id].append(websocket)
    
    try:
        while True:
            # Sadece dinlemiyoruz, tarayıcıdan gelen Ping'lere yanıt veriyoruz!
            data = await websocket.receive_text()
            if data == "PING":
                await websocket.send_text('{"type": "PONG"}')
                print(f"[WS] ODA {room_id}: Istemciden Ping alindi.", flush=True)
                
    except WebSocketDisconnect as e:
        print(f"[WS]  ODA {room_id}: Istemci normal bir sekilde koptu. (Kod: {e.code})", flush=True)
    except Exception as e:
        # İŞTE BİZİ KURTARACAK SATIR BURASI! Çökerse sebebi buraya düşecek.
        print(f"[WS]  ODA {room_id}: BEKLENMEYEN KOPMA HATASI! -> {str(e)}", flush=True)
        traceback.print_exc() 
    finally:
        if room_id in active_rooms and websocket in active_rooms[room_id]:
            active_rooms[room_id].remove(websocket)
        if room_id in active_rooms and len(active_rooms[room_id]) == 0:
            del active_rooms[room_id]
        print(f"[WS] ODA {room_id}: Baglanti tamamen temizlendi.", flush=True)


@app.get("/api/v1/active-rooms")
def get_active_rooms():
    current_time = time.time()
    # Sadece son 5 saniye içinde Delphi'den veri almış "Gerçekten Canlı" odaları listele
    live_rooms = [r_id for r_id, last_seen in active_streams.items() if current_time - last_seen < 5]
    return {"status": "success", "active_rooms": live_rooms}



# ====================================================================
# BÖLÜM 2: FORMULA 1 GEÇMİŞ VERİ (REST API)
# ====================================================================

@app.get("/")
@limiter.limit("30/minute")
def read_root(request: Request):
    return {"message": "Telemetria API Sistemine Hoş Geldiniz. Motorlar çalışıyor!"}

# 1. TEKLİ PİLOT TELEMETRİSİ (Lap by Lap & Track Map destekli)
@app.get("/api/v1/telemetry/{race_year}/{race_name}/{session_type}/{driver_code}")
@limiter.limit("30/minute")
def get_telemetry(request: Request, race_year: int, race_name: str, session_type: str, driver_code: str, lap: str = "fastest"):
    cache_key = f"telemetry_{race_year}_{race_name}_{session_type}_{driver_code}_{lap}"
    cached_response = get_from_cache(cache_key)
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response
        
    telemetry_response = get_lap_telemetry(race_year, race_name, session_type, driver_code, lap)
    
    if isinstance(telemetry_response, dict) and "error_message" in telemetry_response:
        raise HTTPException(status_code=400, detail=telemetry_response["error_message"])
        
    final_response = {
        "status": "success", "cache": "miss", "driver_code": driver_code,
        "track_name": race_name, "lap_requested": lap,
        "data_points": len(telemetry_response.get("time", [])),
        "telemetry_data": telemetry_response
    }
    set_to_cache(cache_key, final_response)
    return final_response

# 2. İKİ PİLOTU KARŞILAŞTIRMA VE DELTA HESAPLAMA ENDPOINT'İ
@app.get("/api/v1/compare/{race_year}/{race_name}/{session_type}/{driver1}/{driver2}")
@limiter.limit("15/minute")
def get_compare(request: Request, race_year: int, race_name: str, session_type: str, driver1: str, driver2: str, lap: str = "fastest"):
    cache_key = f"compare_v5{race_year}_{race_name}_{session_type}_{driver1}_{driver2}_{lap}"
    cached_response = get_from_cache(cache_key)
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    compare_response = get_comparison_telemetry(race_year, race_name, session_type, driver1, driver2, lap)

    if isinstance(compare_response, dict) and "error_message" in compare_response:
        raise HTTPException(status_code=400, detail=compare_response["error_message"])

    final_response = {
        "status": "success", "cache": "miss", "track_name": race_name,
        "lap_requested": lap, "comparison_data": compare_response
    }
    set_to_cache(cache_key, final_response)
    return final_response

# Yardımcı takvim uç noktaları
app.include_router(sessions.router, prefix="/api/v1/schedule", tags=["Schedule"])

# 3. PİLOTUN TÜM TURLARI VE SEKTÖR ZAMANLARI (Lap Summary)
@app.get("/api/v1/laps/{race_year}/{race_name}/{session_type}/{driver_code}")
@limiter.limit("40/minute")
def get_laps_summary(request: Request, race_year: int, race_name: str, session_type: str, driver_code: str):
    cache_key = f"laps_summary_v2{race_year}_{race_name}_{session_type}_{driver_code}"
    cached_response = get_from_cache(cache_key)
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    laps_response = get_driver_laps_summary(race_year, race_name, session_type, driver_code)

    if isinstance(laps_response, dict) and "error_message" in laps_response:
        raise HTTPException(status_code=400, detail=laps_response["error_message"])

    final_response = {
        "status": "success", "cache": "miss", "driver_code": driver_code,
        "track_name": race_name, "session_type": session_type,
        "total_laps": len(laps_response.get("laps", [])),
        "laps_data": laps_response["laps"]
    }
    set_to_cache(cache_key, final_response)
    return final_response