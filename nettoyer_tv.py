#!/usr/bin/env python3
"""Nettoie une télé Philips Google TV via ADB : moins de pubs, moins d'applis en fond.

Tout est réversible : les applis système sont *désactivées* (pas supprimées) et
la liste est enregistrée dans un fichier de sauvegarde pour --restaurer.

Prérequis (une seule fois) :
  1. Sur la télé : Paramètres > Système > À propos > cliquer 7 fois sur « Build ».
  2. Paramètres > Système > Options pour les développeurs > « Débogage USB » activé.
  3. Sur l'ordinateur (même wifi) : installer adb (« platform-tools » Android).

Usage :
    python3 nettoyer_tv.py                     # simulation : montre ce qui serait fait
    python3 nettoyer_tv.py --appliquer         # applique, avec confirmation par appli
    python3 nettoyer_tv.py --restaurer         # réactive tout ce qui a été désactivé
    python3 nettoyer_tv.py --ip 192.168.1.20   # adresse de la télé (défaut : 192.168.1.20)
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_IP = "192.168.1.20"
SAUVEGARDE = Path(__file__).with_name("sauvegarde_tv.json")

# Applis système : désactivées avec « pm disable-user » (réactivables).
# Uniquement des paquets connus pour être sans risque sur Google TV.
SYSTEME = {
    "Pubs et recommandations": {
        "com.google.android.tvrecommendations": "recommandations sponsorisées (ancien écran d'accueil)",
        "com.google.android.leanbacklauncher.recommendations": "recommandations de l'écran d'accueil",
        "com.google.android.apps.tv.dreamx": "économiseur d'écran Google (affiche des suggestions)",
        "com.google.android.feedback": "envoi de rapports à Google",
    },
    "Services inutiles en arrière-plan": {
        "com.google.android.play.games": "Google Play Jeux",
        "com.android.printspooler": "service d'impression",
        "com.google.android.marvin.talkback": "lecteur d'écran (accessibilité)",
    },
}

# Applis tierces préinstallées : désinstallées pour l'utilisateur seulement
# (« pm uninstall --user 0 »), récupérables avec « cmd package install-existing ».
TIERCES = {
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.spotify.tv.android": "Spotify",
    "tv.wuaki.apptv": "Rakuten TV",
    "tv.pluto.android": "Pluto TV (gratuit avec pubs)",
    "com.zattoo.player": "Zattoo",
    "com.google.android.youtube.tvmusic": "YouTube Music",
    "com.google.android.youtube.tvkids": "YouTube Kids",
    "com.crunchyroll.crunchyroid": "Crunchyroll",
    "com.disney.disneyplus": "Disney+",
    "com.netflix.ninja": "Netflix",
    "com.canal.android.canal": "CANAL+",
}

# Animations accélérées : l'interface paraît bien plus réactive.
REGLAGES = {
    "window_animation_scale": ("0.5", "1.0"),
    "transition_animation_scale": ("0.5", "1.0"),
    "animator_duration_scale": ("0.5", "1.0"),
}


def adb(*args, check=True):
    r = subprocess.run(["adb", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout.strip()


def shell(cmd):
    return adb("shell", cmd, check=False)


def connecter(ip):
    if not shutil.which("adb"):
        sys.exit("adb introuvable : installe les « platform-tools » Android puis relance.")
    print(f"Connexion à {ip}…  (accepte l'autorisation qui s'affiche sur la télé)")
    sortie = adb("connect", f"{ip}:5555", check=False)
    etat = adb("get-state", check=False)
    if etat != "device":
        sys.exit(
            f"Connexion impossible ({sortie}).\n"
            "Vérifie le « Débogage USB » sur la télé et accepte la fenêtre d'autorisation, puis relance."
        )
    modele = shell("getprop ro.product.model")
    print(f"Connecté : {modele}\n")


def paquets_installes():
    return {l.removeprefix("package:") for l in shell("pm list packages").splitlines()}


def paquets_desactives():
    return {l.removeprefix("package:") for l in shell("pm list packages -d").splitlines()}


def demander(question, auto):
    if auto:
        return True
    return input(f"{question} [o/N] ").strip().lower() in ("o", "oui", "y")


def nettoyer(appliquer, auto):
    installes = paquets_installes()
    deja = paquets_desactives()
    sauvegarde = {"desactives": [], "desinstalles": []}
    if SAUVEGARDE.exists():
        sauvegarde = json.loads(SAUVEGARDE.read_text())

    for categorie, paquets in SYSTEME.items():
        print(f"== {categorie} ==")
        for pkg, desc in paquets.items():
            if pkg not in installes:
                continue
            if pkg in deja:
                print(f"  déjà désactivé : {desc}")
                continue
            if not appliquer:
                print(f"  serait désactivé : {desc}  ({pkg})")
            elif demander(f"  Désactiver {desc} ?", auto):
                print("   ", shell(f"pm disable-user --user 0 {pkg}") or "ok")
                sauvegarde["desactives"].append(pkg)
        print()

    print("== Applis préinstallées (garde celles que tu utilises !) ==")
    for pkg, nom in TIERCES.items():
        if pkg not in installes:
            continue
        if not appliquer:
            print(f"  pourrait être désinstallée : {nom}  ({pkg})")
        # Jamais en automatique : c'est à toi de choisir tes applis.
        elif demander(f"  Désinstaller {nom} ?", False):
            print("   ", shell(f"pm uninstall --user 0 {pkg}") or "ok")
            sauvegarde["desinstalles"].append(pkg)
    print()

    print("== Réactivité ==")
    for cle, (valeur, _) in REGLAGES.items():
        if appliquer:
            shell(f"settings put global {cle} {valeur}")
        print(f"  {cle} = {valeur}")
    if appliquer:
        shell("pm trim-caches 999G")
        print("  caches des applis vidés")
    print()

    if appliquer:
        SAUVEGARDE.write_text(json.dumps(sauvegarde, indent=2))
        print(f"Sauvegarde : {SAUVEGARDE}  (pour --restaurer)")
        if demander("Redémarrer la télé maintenant ?", auto):
            shell("reboot")
    else:
        print("Simulation uniquement. Relance avec --appliquer pour effectuer les changements.")


def restaurer():
    if not SAUVEGARDE.exists():
        sys.exit(f"Pas de sauvegarde ({SAUVEGARDE}).")
    sauvegarde = json.loads(SAUVEGARDE.read_text())
    for pkg in sauvegarde["desactives"]:
        print(f"réactive {pkg} :", shell(f"pm enable {pkg}") or "ok")
    for pkg in sauvegarde["desinstalles"]:
        print(f"réinstalle {pkg} :", shell(f"cmd package install-existing {pkg}") or "ok")
    for cle, (_, defaut) in REGLAGES.items():
        shell(f"settings put global {cle} {defaut}")
    SAUVEGARDE.unlink()
    print("Restauration terminée.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ip", default=DEFAULT_IP, help=f"adresse de la télé (défaut {DEFAULT_IP})")
    parser.add_argument("--appliquer", action="store_true", help="effectue les changements")
    parser.add_argument("--oui", action="store_true", help="ne pas demander pour les applis système")
    parser.add_argument("--restaurer", action="store_true", help="annule tous les changements")
    args = parser.parse_args()

    connecter(args.ip)
    if args.restaurer:
        restaurer()
    else:
        nettoyer(args.appliquer, args.oui)


if __name__ == "__main__":
    main()
