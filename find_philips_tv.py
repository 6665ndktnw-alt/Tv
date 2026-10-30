#!/usr/bin/env python3
"""Trouve les téléviseurs Philips sur le réseau local (wifi / ethernet).

Deux méthodes, sans dépendance externe (Python 3.8+) :
  1. SSDP / UPnP : diffusion multicast, la télé répond si elle est allumée.
  2. Scan JointSpace : teste les ports 1925 (HTTP) et 1926 (HTTPS) de l'API
     Philips sur chaque adresse du sous-réseau local.

Usage :
    python3 find_philips_tv.py              # SSDP puis scan du sous-réseau
    python3 find_philips_tv.py --subnet 192.168.1.0/24
    python3 find_philips_tv.py --no-scan    # SSDP uniquement
"""

import argparse
import ipaddress
import json
import socket
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

SSDP_ADDR = ("239.255.255.250", 1900)
JOINTSPACE_PORTS = (1925, 1926)
API_VERSIONS = (6, 5, 1)

# Les télés Android Philips utilisent un certificat auto-signé sur le port 1926.
_INSECURE_CTX = ssl.create_default_context()
_INSECURE_CTX.check_hostname = False
_INSECURE_CTX.verify_mode = ssl.CERT_NONE


def local_ip():
    """Adresse IP de cette machine sur le réseau local."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]


def fetch(url, timeout=2.0):
    with urllib.request.urlopen(url, timeout=timeout, context=_INSECURE_CTX) as r:
        return r.read()


def ssdp_discover(timeout=4.0):
    """Envoie un M-SEARCH SSDP et renvoie {ip: description} des appareils Philips."""
    msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 3\r\n"
        "ST: ssdp:all\r\n\r\n"
    ).encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)
    for _ in range(2):
        sock.sendto(msg, SSDP_ADDR)

    locations = {}
    try:
        while True:
            data, (ip, _) = sock.recvfrom(65507)
            headers = {}
            for line in data.decode(errors="ignore").split("\r\n")[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            if "location" in headers:
                locations.setdefault(ip, set()).add(headers["location"])
    except socket.timeout:
        pass
    finally:
        sock.close()

    found = {}
    for ip, urls in locations.items():
        for url in urls:
            try:
                root = ET.fromstring(fetch(url))
            except Exception:
                continue
            info = {el.tag.split("}")[-1]: (el.text or "").strip() for el in root.iter()}
            text = " ".join(info.get(k, "") for k in ("manufacturer", "friendlyName", "modelName"))
            if "philips" in text.lower() or "tp vision" in text.lower():
                found[ip] = {
                    "nom": info.get("friendlyName"),
                    "modèle": info.get("modelName"),
                    "fabricant": info.get("manufacturer"),
                }
                break
    return found


def probe_jointspace(ip):
    """Interroge l'API JointSpace Philips ; renvoie les infos système ou None."""
    for port in JOINTSPACE_PORTS:
        scheme = "https" if port == 1926 else "http"
        try:
            with socket.create_connection((str(ip), port), timeout=0.4):
                pass
        except OSError:
            continue
        for version in API_VERSIONS:
            try:
                system = json.loads(fetch(f"{scheme}://{ip}:{port}/{version}/system"))
            except Exception:
                continue
            return {
                "nom": system.get("name"),
                "modèle": system.get("model") or system.get("ctn"),
                "api": f"{scheme}://{ip}:{port}/{version}/",
                "pairing requis": "pairing" in json.dumps(system.get("featuring", {})).lower(),
            }
        # Port ouvert mais /system protégé : c'est quand même très probablement une Philips.
        return {"api": f"{scheme}://{ip}:{port}/", "note": "port JointSpace ouvert"}
    return None


def scan_subnet(network):
    hosts = list(ipaddress.ip_network(network, strict=False).hosts())
    print(f"Scan de {len(hosts)} adresses sur {network} (ports {JOINTSPACE_PORTS})…")
    with ThreadPoolExecutor(max_workers=64) as pool:
        results = pool.map(probe_jointspace, hosts)
    return {str(ip): info for ip, info in zip(hosts, results) if info}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subnet", help="ex. 192.168.1.0/24 (détecté automatiquement sinon)")
    parser.add_argument("--no-scan", action="store_true", help="SSDP uniquement")
    args = parser.parse_args()

    print("Recherche SSDP/UPnP…")
    tvs = ssdp_discover()

    if not args.no_scan:
        subnet = args.subnet or f"{local_ip()}/24"
        for ip, info in scan_subnet(subnet).items():
            tvs.setdefault(ip, {}).update(info)

    if not tvs:
        print("\nAucune télé Philips trouvée. Vérifie que :")
        print("  - la télé est allumée (pas en veille profonde) et connectée au wifi ;")
        print("  - cet ordinateur est sur le même réseau (pas un wifi invité) ;")
        print("  - l'option « Allumer avec Wi-Fi (WoWLAN) » / réseau est activée sur la télé.")
        return 1

    print(f"\n{len(tvs)} télé(s) Philips trouvée(s) :")
    for ip, info in sorted(tvs.items()):
        print(f"\n  IP : {ip}")
        for k, v in info.items():
            if v not in (None, ""):
                print(f"    {k} : {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
