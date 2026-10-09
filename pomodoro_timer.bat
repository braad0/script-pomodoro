@echo off


echo [Pomodoro] Chargement du timer...

powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; .\pomodoro_timer.ps1"

echo [Pomodoro] Timer lance en arriere-plan.
echo [Pomodoro] Fermez cette fenetre, le timer continue.
