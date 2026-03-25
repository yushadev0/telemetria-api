import fastf1
import os
import pandas as pd
import numpy as np

# Önbellek klasörünü belirliyoruz
cache_dir = "f1_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

fastf1.Cache.enable_cache(cache_dir)

def get_lap_telemetry(race_year: int, race_name: str, session_type: str, driver_code: str, lap_param: str = "fastest", sample_rate: int = 5):
    try:
        f1_session = fastf1.get_session(race_year, race_name, session_type)
        f1_session.load(telemetry=True, weather=False, messages=False)

        # Pilotun tüm turlarını çek
        driver_laps = f1_session.laps.pick_drivers(driver_code)

        # Lap by Lap Optimizasyonu: Parametre "fastest" ise en hızlıyı, sayı ise o turu al
        if str(lap_param).lower() == "fastest":
            target_lap = driver_laps.pick_fastest()
        else:
            target_lap = driver_laps[driver_laps['LapNumber'] == float(lap_param)].iloc[0]

        telemetry_data = target_lap.get_telemetry()
        
        # Track Map İçin X, Y, Z Koordinatlarını Ekliyoruz
        columns_to_keep = ['Time', 'Distance', 'Speed', 'nGear', 'Throttle', 'Brake', 'DRS', 'X', 'Y', 'Z']
        filtered_telemetry = telemetry_data[columns_to_keep].copy()
        
        sampled_telemetry = filtered_telemetry.iloc[::sample_rate, :].copy()
        sampled_telemetry['Time'] = sampled_telemetry['Time'].dt.total_seconds()
        
        # Tüm anahtarları snake_case formatına çeviriyoruz
        sampled_telemetry.rename(columns={
            'Time': 'time',
            'Distance': 'distance',
            'Speed': 'speed',
            'nGear': 'n_gear',
            'Throttle': 'throttle',
            'Brake': 'brake',
            'DRS': 'drs',
            'X': 'x',
            'Y': 'y',
            'Z': 'z'
        }, inplace=True)
        
        # orient="records" yerine orient="list" kullanarak dizilere çeviriyoruz
        final_result = sampled_telemetry.fillna(0).to_dict(orient="list")
        
        # UI tarafında tur zamanını gösterebilmek için ekstra meta veriler
        final_result["lap_number"] = int(target_lap['LapNumber'])
        final_result["lap_time"] = target_lap['LapTime'].total_seconds() if pd.notna(target_lap['LapTime']) else None
        
        return final_result

    except Exception as error_message:
        return {"error_message": str(error_message)}

def get_comparison_telemetry(race_year: int, race_name: str, session_type: str, driver1: str, driver2: str, lap_param: str = "fastest"):
    """ İki pilotun telemetrisini Sabit Mesafe (Fixed Distance) ile kıyaslar ve Delta zamanı hesaplar """
    try:
        f1_session = fastf1.get_session(race_year, race_name, session_type)
        f1_session.load(telemetry=True, weather=False, messages=False)
        
        laps_d1 = f1_session.laps.pick_drivers(driver1)
        laps_d2 = f1_session.laps.pick_drivers(driver2)
        
        if str(lap_param).lower() == "fastest":
            lap1 = laps_d1.pick_fastest()
            lap2 = laps_d2.pick_fastest()
        else:
            lap1 = laps_d1[laps_d1['LapNumber'] == float(lap_param)].iloc[0]
            lap2 = laps_d2[laps_d2['LapNumber'] == float(lap_param)].iloc[0]
            
        tel1 = lap1.get_telemetry()
        tel2 = lap2.get_telemetry()
        
        time1 = tel1['Time'].dt.total_seconds().values
        time2 = tel2['Time'].dt.total_seconds().values
        dist1 = tel1['Distance'].values
        dist2 = tel2['Distance'].values
        
        # FIXED DISTANCE DOWNSAMPLING
        # Kesişen maksimum mesafeyi bul ve her 5 metrede bir ölçüm ekseni oluştur
        max_distance = min(np.max(dist1), np.max(dist2))
        fixed_distances = np.arange(0, max_distance, 5)
        
        # Pilot 1 Numpy Interpolasyonu (Veriyi yeni eksene oturtma)
        d1_time = np.interp(fixed_distances, dist1, time1)
        d1_speed = np.interp(fixed_distances, dist1, tel1['Speed'].values)
        d1_throttle = np.interp(fixed_distances, dist1, tel1['Throttle'].values)
        d1_brake = np.interp(fixed_distances, dist1, tel1['Brake'].values)
        d1_gear = np.interp(fixed_distances, dist1, tel1['nGear'].values)
        
        # Pilot 2 Numpy Interpolasyonu
        d2_time = np.interp(fixed_distances, dist2, time2)
        d2_speed = np.interp(fixed_distances, dist2, tel2['Speed'].values)
        d2_throttle = np.interp(fixed_distances, dist2, tel2['Throttle'].values)
        d2_brake = np.interp(fixed_distances, dist2, tel2['Brake'].values)
        d2_gear = np.interp(fixed_distances, dist2, tel2['nGear'].values)
        
        # DELTA HESAPLAMASI: Pilot 1'e göre Pilot 2'nin zaman farkı
        delta_time = d1_time - d2_time

        # NaN verileri numpy ile sıfırlayıp liste olarak JSON'a hazırlıyoruz
        return {
            "fixed_distance": fixed_distances.tolist(),
            "delta_time": np.nan_to_num(delta_time).tolist(),
            "driver1": {
                "code": driver1,
                "lap_time": lap1['LapTime'].total_seconds() if pd.notna(lap1['LapTime']) else None,
                "speed": np.nan_to_num(d1_speed).tolist(),
                "throttle": np.nan_to_num(d1_throttle).tolist(),
                "brake": np.nan_to_num(d1_brake).tolist(),
                "n_gear": np.round(np.nan_to_num(d1_gear)).tolist()
            },
            "driver2": {
                "code": driver2,
                "lap_time": lap2['LapTime'].total_seconds() if pd.notna(lap2['LapTime']) else None,
                "speed": np.nan_to_num(d2_speed).tolist(),
                "throttle": np.nan_to_num(d2_throttle).tolist(),
                "brake": np.nan_to_num(d2_brake).tolist(),
                "n_gear": np.round(np.nan_to_num(d2_gear)).tolist()
            }
        }
    except Exception as e:
        return {"error_message": str(e)}
    
def get_driver_laps_summary(race_year: int, race_name: str, session_type: str, driver_code: str):
    """
    Pilotun o seanstaki tüm turlarının özetini, sektör zamanlarını ve lastik bilgisini getirir.
    telemetry=False olduğu için inanılmaz hızlı çalışır.
    """
    try:
        f1_session = fastf1.get_session(race_year, race_name, session_type)
        # SİHİR BURADA: telemetry=False dediğimiz için sadece tur tablolarını yükler, çok hızlıdır!
        f1_session.load(telemetry=False, weather=False, messages=False)

        driver_laps = f1_session.laps.pick_drivers(driver_code)
        
        laps_data = []
        for _, row in driver_laps.iterrows():
            # Geçersiz/Silinmiş turları (LapTime NaN olanları) filtreleyebiliriz ama pite giriş çıkışları
            # görmek için null (None) olarak göndermek UI tarafında daha değerlidir.
            
            laps_data.append({
                "lap_number": int(row['LapNumber']) if pd.notna(row['LapNumber']) else None,
                "lap_time": row['LapTime'].total_seconds() if pd.notna(row['LapTime']) else None,
                "sector_1": row['Sector1Time'].total_seconds() if pd.notna(row['Sector1Time']) else None,
                "sector_2": row['Sector2Time'].total_seconds() if pd.notna(row['Sector2Time']) else None,
                "sector_3": row['Sector3Time'].total_seconds() if pd.notna(row['Sector3Time']) else None,
                "compound": str(row['Compound']) if pd.notna(row['Compound']) else "UNKNOWN",
                "tyre_life": int(row['TyreLife']) if pd.notna(row['TyreLife']) else None,
                "is_personal_best": bool(row['IsPersonalBest']) if pd.notna(row['IsPersonalBest']) else False,
                # Pite girilen veya pitten çıkılan turları UI'da ikonla göstermek için:
                "is_pit_out": True if pd.notna(row['PitOutTime']) else False,
                "is_pit_in": True if pd.notna(row['PitInTime']) else False
            })

        return {"laps": laps_data}

    except Exception as e:
        return {"error_message": str(e)}