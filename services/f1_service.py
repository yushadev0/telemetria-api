import fastf1
import os
import threading
from collections import OrderedDict
import pandas as pd
import numpy as np

# Önbellek klasörünü belirliyoruz
cache_dir = "f1_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

fastf1.Cache.enable_cache(cache_dir)

# Prod'da FastF1'in ayrintili INFO log'lari NSSM ile diske yaziliyor -> gurultu + I/O.
# Sadece uyari ve ustunu birak (FASTF1_LOG env ile degistirilebilir).
try:
    fastf1.set_log_level(os.getenv("FASTF1_LOG", "WARNING"))
except Exception:
    pass

# ---------------------------------------------------------------------------
# B4: Yuklenmis FastF1 Session nesnelerini process icinde tut.
#   - telemetry / compare  -> ayni (year,race,session) icin TEK load(telemetry=True)
#   - laps / drivers       -> ayni seans icin TEK load(telemetry=False)
# Onceden her endpoint her cagride bastan get_session().load() yapiyordu (~15-40 sn).
# Tam yuklu session nesneleri buyuktur; kac tane tutulacagi SESSION_CACHE_MAX ile ayarlanir.
# ---------------------------------------------------------------------------
_SESSION_CACHE_MAX = int(os.getenv("SESSION_CACHE_MAX", "4"))
_session_cache = OrderedDict()            # skey -> loaded fastf1 Session
_session_cache_lock = threading.Lock()   # _session_cache sozlugunu korur
_load_locks = {}                         # skey -> Lock (ayni seansi iki kez yuklememek icin)
_load_locks_guard = threading.Lock()


def _skey(race_year, race_name, session_type, with_telemetry):
    return (int(race_year), str(race_name).strip().lower(),
            str(session_type).strip().upper(), bool(with_telemetry))


def _load_lock_for(skey):
    with _load_locks_guard:
        lk = _load_locks.get(skey)
        if lk is None:
            lk = threading.Lock()
            _load_locks[skey] = lk
        return lk


def get_loaded_session(race_year, race_name, session_type, with_telemetry=True):
    """(year,race,session,with_telemetry) icin yuklenmis Session'i dondurur; yoksa yukler ve cache'ler."""
    skey = _skey(race_year, race_name, session_type, with_telemetry)

    with _session_cache_lock:
        sess = _session_cache.get(skey)
        if sess is not None:
            _session_cache.move_to_end(skey)
            return sess

    # Yukleme uzun surer: ayni seans icin serilestir, farkli seanslar paralel yuklensin.
    with _load_lock_for(skey):
        with _session_cache_lock:
            sess = _session_cache.get(skey)
            if sess is not None:
                _session_cache.move_to_end(skey)
                return sess

        sess = fastf1.get_session(race_year, race_name, session_type)
        sess.load(telemetry=with_telemetry, weather=False, messages=False)

        with _session_cache_lock:
            _session_cache[skey] = sess
            while len(_session_cache) > _SESSION_CACHE_MAX:
                _session_cache.popitem(last=False)
        return sess

def get_lap_telemetry(race_year: int, race_name: str, session_type: str, driver_code: str, lap_param: str = "fastest", sample_rate: int = 5):
    try:
        f1_session = get_loaded_session(race_year, race_name, session_type, with_telemetry=True)

        # Pilotun tüm turlarını çek
        driver_laps = f1_session.laps.pick_drivers(driver_code)

        # Lap by Lap Optimizasyonu: Parametre "fastest" ise en hızlıyı, sayı ise o turu al
        if str(lap_param).lower() == "fastest":
            target_lap = driver_laps.pick_fastest()
        else:
            target_lap = driver_laps[driver_laps['LapNumber'] == float(lap_param)].iloc[0]

        telemetry_data = target_lap.get_telemetry()

        # Track Map icin X, Y yeterli (2D). Z kolonu frontend'de kullanilmiyor -> atildi.
        columns_to_keep = ['Time', 'Distance', 'Speed', 'nGear', 'Throttle', 'Brake', 'DRS', 'X', 'Y']
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
            'Y': 'y'
        }, inplace=True)

        sampled_telemetry = sampled_telemetry.fillna(0)

        # B6: JSON boyutunu kucult - gereksiz ondalik haneleri kirp / tamsayiya cek.
        # (ornek: "243.617899999" -> 243.6 ; "1234.0" -> 1234)  ~30-40% daha kucuk govde.
        sampled_telemetry['time'] = sampled_telemetry['time'].round(3)
        sampled_telemetry['distance'] = sampled_telemetry['distance'].round(1)
        sampled_telemetry['speed'] = sampled_telemetry['speed'].round(1)
        for _c in ('n_gear', 'drs', 'x', 'y', 'throttle'):
            sampled_telemetry[_c] = sampled_telemetry[_c].round(0).astype('int64')

        # orient="records" yerine orient="list" kullanarak dizilere çeviriyoruz
        final_result = sampled_telemetry.to_dict(orient="list")

        # UI tarafında tur zamanını gösterebilmek için ekstra meta veriler
        final_result["lap_number"] = int(target_lap['LapNumber'])
        final_result["lap_time"] = round(target_lap['LapTime'].total_seconds(), 3) if pd.notna(target_lap['LapTime']) else None
        
        return final_result

    except Exception as error_message:
        return {"error_message": str(error_message)}

def get_comparison_telemetry(race_year: int, race_name: str, session_type: str, driver1: str, driver2: str, lap_param: str = "fastest"):
    """ İki pilotun telemetrisini Sabit Mesafe (Fixed Distance) ile kıyaslar ve Delta zamanı hesaplar """
    try:
        f1_session = get_loaded_session(race_year, race_name, session_type, with_telemetry=True)

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
        max_distance = min(np.max(dist1), np.max(dist2))
        fixed_distances = np.arange(0, max_distance, 5)
        
        # Pilot 1 Numpy Interpolasyonu
        d1_time = np.interp(fixed_distances, dist1, time1)
        d1_speed = np.interp(fixed_distances, dist1, tel1['Speed'].values)
        d1_throttle = np.interp(fixed_distances, dist1, tel1['Throttle'].values)
        d1_brake = np.interp(fixed_distances, dist1, tel1['Brake'].values)
        d1_gear = np.interp(fixed_distances, dist1, tel1['nGear'].values)
        d1_x = np.interp(fixed_distances, dist1, tel1['X'].values)
        d1_y = np.interp(fixed_distances, dist1, tel1['Y'].values)
        
        # Pilot 2 Numpy Interpolasyonu
        d2_time = np.interp(fixed_distances, dist2, time2)
        d2_speed = np.interp(fixed_distances, dist2, tel2['Speed'].values)
        d2_throttle = np.interp(fixed_distances, dist2, tel2['Throttle'].values)
        d2_brake = np.interp(fixed_distances, dist2, tel2['Brake'].values)
        d2_gear = np.interp(fixed_distances, dist2, tel2['nGear'].values)
        d2_x = np.interp(fixed_distances, dist2, tel2['X'].values)
        d2_y = np.interp(fixed_distances, dist2, tel2['Y'].values)
        
        # DELTA HESAPLAMASI: Pilot 1'e göre Pilot 2'nin zaman farkı
        delta_time = d1_time - d2_time

        # --- İŞTE SENİN MANTIK YÜRÜTÜP EKSİK DEDİĞİ KAHRAMAN DÖNGÜ BURASI ---
        # Şeridi (Ribbon) doldurmak için iki pilotun da tüm turlarını tarayıp listeye atıyoruz.
        laps_overview = []
        max_lap = int(max(laps_d1['LapNumber'].max() if not laps_d1.empty else 0, laps_d2['LapNumber'].max() if not laps_d2.empty else 0))
        
        for ln in range(1, max_lap + 1):
            row1 = laps_d1[laps_d1['LapNumber'] == ln]
            row2 = laps_d2[laps_d2['LapNumber'] == ln]
            
            c1 = str(row1.iloc[0]['Compound']) if not row1.empty and pd.notna(row1.iloc[0]['Compound']) else "UNKNOWN"
            c2 = str(row2.iloc[0]['Compound']) if not row2.empty and pd.notna(row2.iloc[0]['Compound']) else "UNKNOWN"
            
            lt1 = row1.iloc[0]['LapTime'].total_seconds() if not row1.empty and pd.notna(row1.iloc[0]['LapTime']) else None
            lt2 = row2.iloc[0]['LapTime'].total_seconds() if not row2.empty and pd.notna(row2.iloc[0]['LapTime']) else None

            laps_overview.append({
                "lap_number": ln, 
                "d1_compound": c1, 
                "d2_compound": c2,
                "d1_lap_time": lt1, 
                "d2_lap_time": lt2
            })

        return {
            "fixed_distance": fixed_distances.tolist(),
            "delta_time": np.nan_to_num(delta_time).tolist(),
            "laps_overview": laps_overview, # JS'nin beklediği o liste!
            "driver1": {
                "code": driver1,
                "lap_time": lap1['LapTime'].total_seconds() if pd.notna(lap1['LapTime']) else None,
                "speed": np.nan_to_num(d1_speed).tolist(),
                "throttle": np.nan_to_num(d1_throttle).tolist(),
                "brake": np.nan_to_num(d1_brake).tolist(),
                "n_gear": np.round(np.nan_to_num(d1_gear)).tolist(),
                "x": np.nan_to_num(d1_x).tolist(),
                "y": np.nan_to_num(d1_y).tolist(),
                "compound": str(lap1['Compound']) if pd.notna(lap1['Compound']) else "UNKNOWN",
                "tyre_life": int(lap1['TyreLife']) if pd.notna(lap1['TyreLife']) else None
            },
            "driver2": {
                "code": driver2,
                "lap_time": lap2['LapTime'].total_seconds() if pd.notna(lap2['LapTime']) else None,
                "speed": np.nan_to_num(d2_speed).tolist(),
                "throttle": np.nan_to_num(d2_throttle).tolist(),
                "brake": np.nan_to_num(d2_brake).tolist(),
                "n_gear": np.round(np.nan_to_num(d2_gear)).tolist(),
                "x": np.nan_to_num(d2_x).tolist(),
                "y": np.nan_to_num(d2_y).tolist(),
                "compound": str(lap2['Compound']) if pd.notna(lap2['Compound']) else "UNKNOWN",
                "tyre_life": int(lap2['TyreLife']) if pd.notna(lap2['TyreLife']) else None
            }
        }
    except Exception as e:
        return {"error_message": str(e)}
    
def get_driver_laps_summary(race_year: int, race_name: str, session_type: str, driver_code: str):
    """
    Pilotun o seanstaki tüm turlarının özetini getirirken, 
    Gerçek F1 kurallarına göre Sektör Renklerini (Mor, Yeşil, Sarı) hesaplar.
    """
    try:
        # Sadece tur verileri (telemetry=False) -> hizli; drivers endpoint'i ile ayni load'u paylasir.
        f1_session = get_loaded_session(race_year, race_name, session_type, with_telemetry=False)

        all_laps = f1_session.laps
        
        # 1. TÜM SEANSIN EN HIZLI SEKTÖRLERİNİ BUL (Mor 🟣 İçin)
        session_best_s1 = all_laps['Sector1Time'].min()
        session_best_s2 = all_laps['Sector2Time'].min()
        session_best_s3 = all_laps['Sector3Time'].min()

        # 2. SADECE SEÇİLİ PİLOTUN TURLARINI AL
        driver_laps = all_laps.pick_drivers(driver_code)
        
        # 3. PİLOTUN KENDİ EN İYİ SEKTÖRLERİNİ BUL (Yeşil 🟢 İçin)
        personal_best_s1 = driver_laps['Sector1Time'].min()
        personal_best_s2 = driver_laps['Sector2Time'].min()
        personal_best_s3 = driver_laps['Sector3Time'].min()
        
        laps_data = []
        for _, row in driver_laps.iterrows():
            
            # --- SEKTÖR RENKLERİNİ HESAPLAMA ---
            s1_val = row['Sector1Time']
            s2_val = row['Sector2Time']
            s3_val = row['Sector3Time']
            
            s1_color = "yellow"
            s2_color = "yellow"
            s3_color = "yellow"

            if pd.notna(s1_val):
                if s1_val == session_best_s1: s1_color = "purple"
                elif s1_val == personal_best_s1: s1_color = "green"

            if pd.notna(s2_val):
                if s2_val == session_best_s2: s2_color = "purple"
                elif s2_val == personal_best_s2: s2_color = "green"

            if pd.notna(s3_val):
                if s3_val == session_best_s3: s3_color = "purple"
                elif s3_val == personal_best_s3: s3_color = "green"

            # Verileri listeye ekle
            laps_data.append({
                "lap_number": int(row['LapNumber']) if pd.notna(row['LapNumber']) else None,
                "lap_time": row['LapTime'].total_seconds() if pd.notna(row['LapTime']) else None,
                
                # UI'da göstermek için saniye cinsinden değerleri
                "sector_1": s1_val.total_seconds() if pd.notna(s1_val) else None,
                "sector_2": s2_val.total_seconds() if pd.notna(s2_val) else None,
                "sector_3": s3_val.total_seconds() if pd.notna(s3_val) else None,
                
                # API'den direkt CSS sınıflarını (yellow, green, purple) yolluyoruz!
                "s1_color": s1_color,
                "s2_color": s2_color,
                "s3_color": s3_color,
                
                "compound": str(row['Compound']) if pd.notna(row['Compound']) else "UNKNOWN",
                "tyre_life": int(row['TyreLife']) if pd.notna(row['TyreLife']) else None,
                "is_personal_best": bool(row['IsPersonalBest']) if pd.notna(row['IsPersonalBest']) else False,
                "is_pit_out": True if pd.notna(row['PitOutTime']) else False,
                "is_pit_in": True if pd.notna(row['PitInTime']) else False
            })

        return {"laps": laps_data}

    except Exception as e:
        return {"error_message": str(e)}