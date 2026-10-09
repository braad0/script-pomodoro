@echo off

echo [Pomodoro] Chargement du timer...
echo [Pomodoro] Ouverture du timer dans une nouvelle fenetre...

start "Pomodoro Timer" python.exe "%~dp0pomodoro_timer.py"

echo [Pomodoro] Timer lance. Une fenetre de commande s'est ouverte.
echo [Pomodoro] Vous pouvez fermer cette fenetre, le timer continue.
