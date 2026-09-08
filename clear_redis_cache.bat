@echo off
setlocal EnableExtensions
REM ============================================================
REM  Telemetria API - Redis onbellegini temizle
REM  Uygulamanin kendi redis_client'ini kullanir (REDIS_HOST env'e saygi duyar).
REM  Deploy sonrasi eski JSON yanitlari silmek icin calistir.
REM ============================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
pushd "%ROOT%"

if not exist "venv\Scripts\python.exe" (
    echo venv bulunamadi. Once setup.bat calistir.
    goto :error
)

"venv\Scripts\python.exe" -c "from core.redis_client import redis_db_client as r; n=r.dbsize(); r.flushdb(); print(f'Redis onbellegi temizlendi: {n} anahtar silindi.')"
if errorlevel 1 goto :error

popd
endlocal
exit /b 0

:error
echo.
echo !!! HATA - Redis'e baglanilamadi ya da python hatasi. Redis/Memurai calisiyor mu?
popd
endlocal
exit /b 1
