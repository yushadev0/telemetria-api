from fastapi import APIRouter, HTTPException, Request
import fastf1
import pandas as pd
from core.redis_client import get_from_cache, set_to_cache
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()

# Limiter objemizi bu dosya için de oluşturuyoruz
limiter = Limiter(key_func=get_remote_address)

# --- HARİKA DOKUNUŞ: PİST VE GÖRSEL SÖZLÜĞÜ ---
# FastF1'in 'Location' verisini yakalayıp, gerçek pist adını ve senin PNG'lerini eşleştirir
TRACK_DATA = {
    "Melbourne": {"name": "Albert Park Circuit", "file": "Avustralya_GP.png"},
    "Sakhir": {"name": "Bahrain International Circuit", "file": "Bahreyn_GP.png"},
    "Jeddah": {"name": "Jeddah Corniche Circuit", "file": "Cidde_GP.png"},
    "Baku": {"name": "Baku City Circuit", "file": "Baku_GP.png"},
    "Miami": {"name": "Miami International Autodrome", "file": "Miami_GP.png"},
    "Imola": {"name": "Autodromo Enzo e Dino Ferrari", "file": "Imola_GP.png"},
    "Monaco": {"name": "Circuit de Monaco", "file": "Monaco_GP.png"},
    "Barcelona": {"name": "Circuit de Barcelona-Catalunya", "file": "Barcelona_GP.png"},
    "Montmeló": {"name": "Circuit de Barcelona-Catalunya", "file": "Barcelona_GP.png"},
    "Montreal": {"name": "Circuit Gilles-Villeneuve", "file": "Kanada_GP.png"},
    "Spielberg": {"name": "Red Bull Ring", "file": "Avusturya_GP.png"},
    "Silverstone": {"name": "Silverstone Circuit", "file": "Silverstone_GP.png"},
    "Budapest": {"name": "Hungaroring", "file": "Hungaroring_GP.png"},
    "Spa-Francorchamps": {"name": "Circuit de Spa-Francorchamps", "file": "Spa_GP.png"},
    "Zandvoort": {"name": "Circuit Zandvoort", "file": "Zandvoort_GP.png"},
    "Monza": {"name": "Autodromo Nazionale Monza", "file": "Monza_GP.png"},
    "Marina Bay": {"name": "Marina Bay Street Circuit", "file": "Singapur_GP.png"},
    "Singapore": {"name": "Marina Bay Street Circuit", "file": "Singapur_GP.png"},
    "Suzuka": {"name": "Suzuka International Racing Course", "file": "Japonya_GP.png"},
    "Lusail": {"name": "Lusail International Circuit", "file": "Katar_GP.png"},
    "Austin": {"name": "Circuit of the Americas", "file": "COTA_GP.png"},
    "Mexico City": {"name": "Autódromo Hermanos Rodríguez", "file": "Meksika_GP.png"},
    "São Paulo": {"name": "Autódromo José Carlos Pace", "file": "Brezilya_GP.png"},
    "Las Vegas": {"name": "Las Vegas Strip Circuit", "file": "Vegas_GP.png"},
    "Yas Island": {"name": "Yas Marina Circuit", "file": "AbuDabi_GP.png"},
    "Abu Dhabi": {"name": "Yas Marina Circuit", "file": "AbuDabi_GP.png"},
    "Shanghai": {"name": "Shanghai International Circuit", "file": "Cin_GP.png"},
    "Istanbul": {"name": "Istanbul Park", "file": "Istanbul_GP.png"},
    "Hockenheim": {"name": "Hockenheimring", "file": "Hockenheim_GP.png"},
    "Nürburg": {"name": "Nürburgring", "file": "Nurburgring_GP.png"},
    "Portimão": {"name": "Algarve International Circuit", "file": "Portekiz_GP.png"},
    "Mugello": {"name": "Autodromo Internazionale del Mugello", "file": "Mugello_GP.png"},
    "Sochi": {"name": "Sochi Autodrom", "file": "Rusya_GP.png"},
    "Madrid": {"name": "IFEMA Madrid", "file": "Madrid_GP.png"},
    "Le Castellet": {"name": "Circuit Paul Ricard", "file": "Fransiz_GP.png"}
}


@router.get("/years")
@limiter.limit("60/minute") 
def get_available_years(request: Request):
    return {
        "status": "success",
        "available_years": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
    }

@router.get("/{race_year}/races")
@limiter.limit("60/minute")
def get_races_by_year(request: Request, race_year: int):
    cache_key = f"schedule_races_v2{race_year}"
    cached_response = get_from_cache(cache_key)
    
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    try:
        schedule = fastf1.get_event_schedule(race_year)
        official_events = schedule[schedule['EventFormat'] != 'testing']
        
        race_list = []
        for index, row in official_events.iterrows():
            loc = row["Location"]
            
            # Sözlükten pisti bul, bulamazsan güvenlik için varsayılan bir değer ata
            track_info = TRACK_DATA.get(loc, {"name": f"{loc} Circuit", "file": "track_placeholder.png"})
            
            race_list.append({
                "round_number": row["RoundNumber"],
                "country": row["Country"],
                "location": row["Location"],
                "event_name": row["EventName"],
                "event_date": str(row["EventDate"].date()),
                "track_name": track_info["name"],  # YENİ EKLENDİ (Örn: Suzuka International Racing Course)
                "track_image": f"https://hasup.net/assets/tracks/{track_info['file']}" # YENİ EKLENDİ
            })
            
        final_response = {
            "status": "success",
            "cache": "miss",
            "race_year": race_year,
            "total_races": len(race_list),
            "races": race_list
        }
        
        set_to_cache(cache_key, final_response)
        return final_response
        
    except Exception as error_message:
        raise HTTPException(status_code=400, detail=str(error_message))


@router.get("/{race_year}/{race_name}/sessions")
@limiter.limit("60/minute")
def get_sessions_by_race(request: Request, race_year: int, race_name: str):
    safe_race_name = race_name.replace(" ", "_")
    cache_key = f"schedule_sessions_{race_year}_{safe_race_name}"
    
    cached_response = get_from_cache(cache_key)
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    try:
        event = fastf1.get_event(race_year, race_name)
        sessions_list = []
        for i in range(1, 6):
            session_name_key = f"Session{i}"
            session_date_key = f"Session{i}DateUtc"
            if session_name_key in event and pd.notna(event[session_name_key]):
                sessions_list.append({
                    "session_id": i,
                    "session_name": event[session_name_key],
                    "session_date": str(event[session_date_key]) if session_date_key in event else None
                })
                
        final_response = {
            "status": "success",
            "cache": "miss",
            "race_year": race_year,
            "race_name": race_name,
            "total_sessions": len(sessions_list),
            "sessions": sessions_list
        }
        
        set_to_cache(cache_key, final_response)
        return final_response
        
    except Exception as error_message:
        raise HTTPException(status_code=400, detail=str(error_message))


@router.get("/{race_year}/{race_name}/{session_type}/drivers")
@limiter.limit("60/minute")
def get_drivers_by_session(request: Request, race_year: int, race_name: str, session_type: str):
    safe_race_name = race_name.replace(" ", "_")
    cache_key = f"schedule_drivers_{race_year}_{safe_race_name}_{session_type}"
    
    cached_response = get_from_cache(cache_key)
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    try:
        f1_session = fastf1.get_session(race_year, race_name, session_type)
        f1_session.load(telemetry=False, weather=False, messages=False)
        
        drivers_data = []
        for driver_code in f1_session.drivers:
            driver_info = f1_session.get_driver(driver_code)
            drivers_data.append({
                "driver_code": driver_info["Abbreviation"],
                "broadcast_name": driver_info["BroadcastName"],
                "team_name": driver_info["TeamName"],
                "team_color": driver_info["TeamColor"]
            })
            
        final_response = {
            "status": "success",
            "cache": "miss",
            "race_year": race_year,
            "race_name": race_name,
            "session_type": session_type,
            "total_drivers": len(drivers_data),
            "drivers": drivers_data
        }
        
        set_to_cache(cache_key, final_response)
        return final_response
        
    except Exception as error_message:
        raise HTTPException(status_code=400, detail=str(error_message))