@echo off
setlocal EnableExtensions
REM ============================================================
REM  Telemetria API - sunucu ILK KURULUM
REM  Repo klasorunde bir kere calistir. venv olusturur ve
REM  requirements.txt icindeki sabit surumleri yukler.
REM ============================================================

REM --- Python secimi: once 'py -3' launcher, yoksa PATH'teki 'python' ---
REM Belirli surum sabitlemek istersen:  set "PYLAUNCHER=py -3.12"
set "PYLAUNCHER="
py -3 --version >nul 2>&1 && set "PYLAUNCHER=py -3"
if not defined PYLAUNCHER python --version >nul 2>&1 && set "PYLAUNCHER=python"
if not defined PYLAUNCHER (
    echo Python bulunamadi. python.org'dan Python 3.12 kurup PATH'e ekle.
    goto :error
)
echo Kullanilan Python: %PYLAUNCHER%
%PYLAUNCHER% --version

REM Script'in bulundugu klasor (sondaki ters boluk atilir)
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
pushd "%ROOT%"

echo.
echo [1/4] Sanal ortam (venv) olusturuluyor...
if exist "venv\Scripts\python.exe" (
    echo       venv zaten var, atlaniyor.
) else (
    %PYLAUNCHER% -m venv venv
    if errorlevel 1 goto :error
)

echo [2/4] pip guncelleniyor...
"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/4] Bagimliliklar yukleniyor (requirements.txt)...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/4] logs klasoru hazirlaniyor...
if not exist "logs\" mkdir "logs"

echo.
echo === KURULUM TAMAM ===
echo.
echo Sonraki adimlar:
echo   1) Redis / Memurai calisiyor mu:   redis-cli ping   (-^> PONG)
echo   2) NSSM servisini bir kere kur:
echo        nssm install TelemetriaAPI "%ROOT%\venv\Scripts\python.exe"
echo        nssm set TelemetriaAPI AppParameters "-m uvicorn main:app --host 0.0.0.0 --port 8000"
echo        nssm set TelemetriaAPI AppDirectory "%ROOT%"
echo        nssm set TelemetriaAPI AppEnvironmentExtra PYTHONUNBUFFERED=1 REDIS_HOST=localhost
echo        nssm set TelemetriaAPI AppStdout "%ROOT%\logs\out.log"
echo        nssm set TelemetriaAPI AppStderr "%ROOT%\logs\err.log"
echo        nssm set TelemetriaAPI AppRotateFiles 1
echo        nssm set TelemetriaAPI Start SERVICE_AUTO_START
echo        nssm start TelemetriaAPI
echo   3) Firewall:  TCP 8000 (API/WebSocket) ve UDP 4433 (telemetri) acik olmali
echo.
popd
endlocal
exit /b 0

:error
echo.
echo !!! HATA olustu - yukaridaki ciktiya bak, duzeltip tekrar calistir. !!!
popd
endlocal
exit /b 1
