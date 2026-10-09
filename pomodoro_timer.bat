@echo off


echo [Pomodoro] Chargement du timer...

start "Pomodoro Timer" powershell.exe -NoExit -ExecutionPolicy Bypass -Command "& { Set-Location '%~dp0'; .\pomodoro_timer.ps1 }"

echo [Pomodoro] Timer lance en arriere-plan.
echo [Pomodoro] Fermez cette fenetre, le timer continue.
