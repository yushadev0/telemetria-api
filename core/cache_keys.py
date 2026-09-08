"""
Redis cache anahtar ureticileri - TEK KAYNAK.
Hem endpoint'ler hem de prewarm ayni fonksiyonlari kullanir; boylece
anahtar formati bir yerde degisince her yer tutarli kalir.
Not: string formatlari mevcut (canlidaki) anahtarlarla birebir aynidir,
degistirirsen eski cache gecersiz olur.
"""


def telemetry(year, race, session, driver, lap="fastest"):
    return f"telemetry_{year}_{race}_{session}_{driver}_{lap}"


def compare(year, race, session, d1, d2, lap="fastest"):
    return f"compare_v5{year}_{race}_{session}_{d1}_{d2}_{lap}"


def laps_summary(year, race, session, driver):
    return f"laps_summary_v2{year}_{race}_{session}_{driver}"


def schedule_races(year):
    return f"schedule_races_v4{year}"


def schedule_sessions(year, race):
    return f"schedule_sessions_{year}_{str(race).replace(' ', '_')}"


def schedule_drivers(year, race, session):
    return f"schedule_drivers_{year}_{str(race).replace(' ', '_')}_{session}"
