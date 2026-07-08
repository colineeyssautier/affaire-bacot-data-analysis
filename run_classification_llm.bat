@echo off
REM Lance classifier_llm_corpus.py et journalise la sortie.
REM Appelé toutes les 12h par le Planificateur de tâches Windows (tâche "BacotClassificationLLM").

cd /d "%~dp0"
set LOGFILE=logs\classification_llm_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%.log
set LOGFILE=%LOGFILE: =0%

C:\Python314\python.exe classifier_llm_corpus.py >> "%LOGFILE%" 2>&1
