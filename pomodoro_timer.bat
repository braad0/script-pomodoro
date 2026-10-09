@echo off
rem ============================================================================
rem pomodoro_timer.bat
rem
rem Petit outil Pomodoro pour l'équipe.
rem A placer sur le partage \\srv-files\tools\productivite\
rem
rem Double-cliquez pour lancer le timer.
rem ============================================================================

echo [Pomodoro] Chargement du timer...
echo [Pomodoro] Ouverture du timer dans une nouvelle fenetre...

rem Cherche python.exe dans les chemins standards
set PYTHON=
where /q python.exe 2>nul && set PYTHON=python.exe
if not defined PYTHON (
    if exist "%LOCALAPPDATA%\Python\pythonw.exe" set PYTHON="%LOCALAPPDATA%\Python\pythonw.exe"
)
if not defined PYTHON (
    if exist "%ProgramFiles%\Python312\pythonw.exe" set PYTHON="%ProgramFiles%\Python312\pythonw.exe"
)
if not defined PYTHON (
    if exist "%ProgramFiles%\Python311\pythonw.exe" set PYTHON="%ProgramFiles%\Python311\pythonw.exe"
)
if not defined PYTHON (
    if exist "%ProgramFiles%\Python310\pythonw.exe" set PYTHON="%ProgramFiles%\Python310\pythonw.exe"
)
if not defined PYTHON (
    echo [Pomodoro] ERREUR : python.exe introuvable. Installez Python ou corrigez le chemin.
    pause
    exit /b 1
)

start "Pomodoro Timer" %PYTHON% "%~dp0pomodoro_timer.py"

echo [Pomodoro] Timer lance. Une fenetre de commande s'est ouverte.
echo [Pomodoro] Vous pouvez fermer cette fenetre, le timer continue.
