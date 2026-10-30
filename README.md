# Trouver une télé Philips sur le wifi

`find_philips_tv.py` cherche les téléviseurs Philips sur le réseau local :

1. **SSDP/UPnP** : la télé répond à une requête multicast et donne son nom et son modèle.
2. **Scan JointSpace** : teste les ports 1925 (HTTP) et 1926 (HTTPS) de l'API Philips sur tout le sous-réseau.

## Utilisation

À lancer depuis un ordinateur connecté **au même wifi** que la télé (Python 3.8+, aucune installation nécessaire) :

```bash
python3 find_philips_tv.py                         # détection automatique
python3 find_philips_tv.py --subnet 192.168.1.0/24 # forcer le sous-réseau
python3 find_philips_tv.py --no-scan               # SSDP seulement (rapide)
```

Exemple de sortie :

```
1 télé(s) Philips trouvée(s) :

  IP : 192.168.1.42
    nom : Philips 55OLED806
    modèle : 55OLED806/12
    api : https://192.168.1.42:1926/6/
```

## Si rien n'est trouvé

- La télé doit être allumée et connectée au wifi.
- L'ordinateur doit être sur le même réseau (pas le wifi invité, pas de VPN actif).
- Sur la télé : *Réglages > Réseau > Allumer avec Wi-Fi (WoWLAN)* activé.
- Sinon, l'adresse IP s'affiche directement sur la télé : *Réglages > Réseau > Afficher les paramètres réseau*.
