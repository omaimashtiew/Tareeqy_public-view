@echo off
cd /d "C:\Users\Nadeen\Documents\Tareeqy\TareeqyyProject"
call ..\EnvTareeqy\Scripts\activate.bat
python telegram_listener.py
