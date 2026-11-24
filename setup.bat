@echo off
rem One-time setup: installs what the game needs. Safe to run again.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
