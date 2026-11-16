@echo off
rem Asks for admin rights (needed to change files in Program Files), then runs the fix script.
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1" -Uninstall
