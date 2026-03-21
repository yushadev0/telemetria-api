import fastf1
import os
import pandas as pd

# Önbellek klasörünü belirliyoruz
cache_dir = "f1_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

fastf1.Cache.enable_cache(cache_dir)

def get_fastest_lap_telemetry(race_year: int, race_name: str, session_type: str, driver_code: str, sample_rate: int = 5):
    try:
        f1_session = fastf1.get_session(race_year, race_name, session_type)
        f1_session.load(telemetry=True, weather=False, messages=False)

        fastest_lap = f1_session.laps.pick_drivers(driver_code).pick_fastest()
        telemetry_data = fastest_lap.get_telemetry()
        
        columns_to_keep = ['Time', 'Distance', 'Speed', 'nGear', 'Throttle', 'Brake', 'DRS']
        filtered_telemetry = telemetry_data[columns_to_keep].copy()
        
        sampled_telemetry = filtered_telemetry.iloc[::sample_rate, :].copy()
        sampled_telemetry['Time'] = sampled_telemetry['Time'].dt.total_seconds()
        
        # 1. OPTİMİZASYON: Tüm anahtarları kesin snake_case formatına çeviriyoruz
        sampled_telemetry.rename(columns={
            'Time': 'time',
            'Distance': 'distance',
            'Speed': 'speed',
            'nGear': 'n_gear',
            'Throttle': 'throttle',
            'Brake': 'brake',
            'DRS': 'drs'
        }, inplace=True)
        
        # 2. OPTİMİZASYON: orient="records" yerine orient="list" kullanarak 
        # veriyi satır bazlıdan, sütun bazlı (dizi) formata geçiriyoruz.
        final_result = sampled_telemetry.fillna(0).to_dict(orient="list")
        return final_result

    except Exception as error_message:
        return {"error_message": str(error_message)}