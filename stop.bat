@echo off
echo [RealtyVision] Stopping server...

taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *RealtyVision*" > nul 2>&1
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *app.py*" > nul 2>&1

for /f "tokens=2 delims=," %%a in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    wmic process where "ProcessId=%%~a" get CommandLine 2>nul | findstr /i "app.py" > nul
    if not errorlevel 1 taskkill /PID %%~a /F > nul 2>&1
)

echo [RealtyVision] Done.
timeout /t 1 > nul
