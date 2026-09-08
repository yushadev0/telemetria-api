@echo off
setlocal EnableExtensions
REM ============================================================
REM  Telemetria API - GUNCELLEME / yeniden deploy
REM  git pull -> pip install -> NSSM servisini yeniden baslat
REM ============================================================

set "SVC=TelemetriaAPI"
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
pushd "%ROOT%"

if not exist "venv\Scripts\python.exe" (
    echo venv yok. Once setup.bat calistir.
    goto :error
)

echo [1/4] Servis durduruluyor (%SVC%)...
nssm stop %SVC% >nul 2>&1

echo [2/4] Kod cekiliyor (git pull)...
git pull
if errorlevel 1 goto :error

echo [3/4] Bagimliliklar kontrol ediliyor...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/4] Servis baslatiliyor...
nssm restart %SVC%
if errorlevel 1 nssm start %SVC%

timeout /t 2 /nobreak >nul
nssm status %SVC%

echo.
echo === GUNCELLEME TAMAM ===   Loglar: %ROOT%\logs\out.log
popd
endlocal
exit /b 0

:error
echo.
echo !!! HATA - servis su an DURMUS olabilir. Kontrol et:  nssm status %SVC%
popd
endlocal
exit /b 1
