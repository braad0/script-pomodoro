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

powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 2; .\pomodoro_timer.ps1"

echo [Pomodoro] Timer lance en arriere-plan.
echo [Pomodoro] Fermez cette fenetre, le timer continue.
