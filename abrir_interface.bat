@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "%USERPROFILE%\Documents\automatizacao-trabalho\.venv\Scripts\activate.bat" (
  call "%USERPROFILE%\Documents\automatizacao-trabalho\.venv\Scripts\activate.bat"
)
start "" cmd /c "timeout /t 6 >nul & start http://localhost:8501"
python -m streamlit run interface.py
pause
