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

start "Pomodoro Timer" python.exe "%~dp0pomodoro_timer.py"

echo [Pomodoro] Timer lance. Une fenetre de commande s'est ouverte.
echo [Pomodoro] Vous pouvez fermer cette fenetre, le timer continue.
