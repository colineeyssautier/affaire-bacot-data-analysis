@echo off
REM Lance le pipeline d'analyse complet (classification lexicale, classification LLM,
REM graphiques, reconstruction de la base) et journalise la sortie.
REM Appelé toutes les 12h par le Planificateur de tâches Windows (tâche "BacotClassificationLLM").

cd /d "%~dp0"
set LOGFILE=logs\pipeline_analyse_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%

C:\Python314\python.exe orchestrer_pipeline_analyse.py >> "%LOGFILE%" 2>&1
