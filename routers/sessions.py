from fastapi import APIRouter, HTTPException, Request
import fastf1
import pandas as pd
from core.redis_client import get_from_cache, set_to_cache
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()

# Limiter objemizi bu dosya için de oluşturuyoruz
limiter = Limiter(key_func=get_remote_address)

@router.get("/years")
@limiter.limit("60/minute") # Dakikada maksimum 60 istek
def get_available_years(request: Request):
    return {
        "status": "success",
        "available_years": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
    }

@router.get("/{race_year}/races")
@limiter.limit("60/minute")
def get_races_by_year(request: Request, race_year: int):
    cache_key = f"schedule_races_{race_year}"
    cached_response = get_from_cache(cache_key)
    
    if cached_response:
        cached_response["cache"] = "hit"
        return cached_response

    try:
        schedule = fastf1.get_event_schedule(race_year)
        official_events = schedule[schedule['EventFormat'] != 'testing']
        
        race_list = []
        for index, row in official_events.iterrows():
            race_list.append({
                "round_number": row["RoundNumber"],
                "country": row["Country"],
                "location": row["Location"],
                "event_name": row["EventName"],
                "event_date": str(row["EventDate"].date())
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
def get_sessions_by_race(request: Request, race_year: int, race_name: str): # request: Request eklendi!
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
def get_drivers_by_session(request: Request, race_year: int, race_name: str, session_type: str): # request: Request eklendi!
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