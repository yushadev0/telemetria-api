@echo off
setlocal EnableExtensions
REM ============================================================
REM  Telemetria API - GUNCELLEME
REM  nssm stop -> git pull -> nssm start
REM ============================================================

set "SVC=TelemetriaAPI"
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
pushd "%ROOT%"

echo [1/3] Servis durduruluyor (%SVC%)...
nssm stop %SVC%

echo [2/3] Kod cekiliyor (git pull)...
git pull
if errorlevel 1 goto :error

echo [3/3] Servis baslatiliyor (%SVC%)...
nssm start %SVC%
if errorlevel 1 goto :error

timeout /t 2 /nobreak >nul
nssm status %SVC%

echo.
echo === GUNCELLEME TAMAM ===
echo Onbellegi de temizlemek icin: clear_redis_cache.bat
popd
endlocal
exit /b 0

:error
echo.
echo !!! HATA - servis su an DURMUS olabilir. Kontrol et:  nssm status %SVC%
popd
endlocal
exit /b 1
