# Milo

Assistant vocal pour Windows, pensé pour les personnes déficientes visuelles.
On appuie sur **Ctrl+Alt+M**, on parle, et Milo agit puis **confirme à voix haute**.

- 100 % hors ligne : la reconnaissance vocale (Vosk) tourne sur l'ordinateur, rien n'est envoyé sur Internet.
- Aucune interface visuelle nécessaire : bips de début et de fin d'écoute, réponses parlées (voix Windows).
- Compatible avec les lecteurs d'écran : pas de hook clavier, NVDA et JAWS ne sont pas perturbés.

## Ce qu'on peut dire

| Exemple | Effet |
|---|---|
| « volume à quarante », « monte le son », « baisse le son de deux crans », « plus fort » | Volume système |
| « coupe le son », « remets le son », « quel est le volume » | Sourdine, état du son |
| « luminosité à soixante-dix », « baisse la luminosité », « plus clair » | Luminosité de l'écran |
| « cinquante pour cent », « plus », « un peu moins », « encore » | Suite du dernier réglage (volume ou luminosité) |
| « mode sombre », « thème clair » | Thème de Windows |
| « ouvre les paramètres Bluetooth », « paramètres wifi », « réglages du narrateur » | Page des Paramètres Windows |
| « ouvre le bloc-notes », « lance Word », « démarre Google Chrome » | Toute application du menu Démarrer |
| « ferme Chrome », « ferme l'application Word », « ferme la fenêtre » | Fermeture douce (comme la croix : l'appli peut proposer d'enregistrer) |
| « recherche la météo à Paris », « fais une recherche sur… » | Recherche web dans le navigateur par défaut |
| « quelle heure est-il », « on est quel jour », « niveau de batterie » | Informations lues à voix haute |
| « tu es là ? » | Vérifier que Milo écoute |
| « répète », « pardon ? » | Redire la dernière réponse |
| « parle plus lentement », « parle plus vite » | Débit de la voix (retenu dans `config.toml`) |
| « aide », « aide sur les modes » | Rappel des commandes |
| « au revoir Milo » | Quitter |

On peut commencer par « Milo, … » ou non. Les pages de paramètres et les raccourcis
d'applications se complètent dans [`milo/data/commandes.toml`](milo/data/commandes.toml).

## Modes

Un mode retient un ensemble de réglages pour les rappeler d'une phrase.

| Exemple | Effet |
|---|---|
| « enregistre le mode soir » | Mémorise le volume, la sourdine, la luminosité et le thème actuels (les met à jour si le mode existe) |
| « active le mode soir », « passe en mode travail », « mode jeux » | Applique le mode et ouvre ses applications |
| « ajoute Steam au mode jeux », « retire Steam du mode jeux » | Applications ouvertes avec le mode |
| « décris le mode soir », « quels sont mes modes », « supprime le mode soir » | Gestion |

Les modes sont enregistrés dans `modes.json` (à côté de `config.toml`), modifiable à la main.
Chaque clé est facultative : un mode n'applique que ce qu'il contient.

```json
{
  "soir": {"volume": 25, "muet": false, "luminosite": 30, "theme": "sombre", "applications": ["Spotify"]},
  "réunion": {"muet": true}
}
```

## Installation (Windows 10/11)

À faire une fois, de préférence par une personne voyante :

1. Installer [Python](https://www.python.org/downloads/) 3.11 ou plus récent, en cochant **« Add python.exe to PATH »**.
2. Télécharger Milo : sur GitHub, **Code → Download ZIP**, puis extraire le dossier (par exemple dans `Documents\Milo`).
3. Double-cliquer sur **`installer.bat`**. L'installation se commente à voix haute et dure une à quelques minutes.

C'est tout : Milo démarre aussitôt, puis **tout seul à chaque ouverture de session**, sans fenêtre.
Il est aussi dans le menu Démarrer (taper « Milo »). Lancé deux fois, il le signale simplement.
Pour arrêter : « au revoir Milo ». Pour ne plus le démarrer automatiquement : **`desinstaller.bat`**.

`installer.bat --sans-demarrage` installe sans démarrage automatique ni entrée de menu.

Installation manuelle, depuis le dossier du projet :

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python scripts\telecharger_modele.py
.venv\Scripts\python -m milo --installer-raccourcis
.venv\Scripts\python -m milo
```

Réglages (raccourci, micro, vitesse de la voix, moteur de recherche…) : [`config.toml`](config.toml).
Au démarrage, si le son est coupé ou sous 20 %, Milo le remonte et le dit : sans cela,
une personne aveugle n'aurait aucun moyen de savoir qu'il fonctionne (`volume_minimum`).
Si `config.toml` contient une erreur, Milo démarre quand même avec les réglages par défaut
et l'annonce ; toute erreur de démarrage est dite à voix haute et détaillée dans le journal.

## Outils de test

```bash
python -m milo --analyse "monte le son de vingt"   # intention reconnue, rien n'est exécuté
python -m milo --commande "quelle heure est-il"    # exécute une commande écrite, sans micro
python -m milo --wav enregistrement.wav            # transcrit un WAV mono 16 bits et l'analyse
python -m milo --micros                            # liste les micros
python -m pytest                                   # tests unitaires (pip install -r requirements-dev.txt)
```

Journal : `%LOCALAPPDATA%\Milo\milo.log`.

## Fonctionnement

```
raccourci ─► bip ─► micro ─┬─► Vosk, grammaire restreinte (mots des commandes) ─┐
                           └─► Vosk, reconnaissance libre (secours) ─────────────┴─► intention ─► action ─► réponse vocale
```

Le petit modèle français confond facilement « le son » et « leçon » ou « Milo » et « Millau ».
Le décodeur à grammaire restreinte ne connaît que les mots des commandes, des pages de
paramètres et des applications installées, ce qui supprime ces confusions. Quand il ne
reconnaît rien d'exécutable (mot hors vocabulaire), Milo se rabat sur la reconnaissance
libre. La correspondance des noms d'applications est volontairement stricte : mieux vaut
« je n'ai pas trouvé » qu'une mauvaise application ouverte sans que l'utilisateur le voie.

| Module | Rôle |
|---|---|
| `milo/intents.py` | Phrase → intention (pur Python, testé) |
| `milo/assistant.py` | Choix de la transcription, exécution, phrase de réponse |
| `milo/stt.py`, `milo/vocabulary.py` | Reconnaissance Vosk et grammaire |
| `milo/modes.py` | Modes enregistrés (`modes.json`) |
| `milo/actions/` | Volume (pycaw), luminosité (screen-brightness-control), thème, fenêtres, paramètres et applis, infos |
| `milo/feedback.py` | Voix SAPI interruptible, bips |
| `milo/hotkey.py` | Raccourci global (`RegisterHotKey`) |

## Feuille de route

- Mot d'éveil « Milo » (sans raccourci clavier), via openWakeWord.
- Modes : fermer des applications, mode avion, « ne pas déranger », éclairage nocturne.
- Activation automatique d'un mode à une heure donnée (« mode soir à 21 heures »).
- Icône dans la zone de notification.
- Exécutable autonome (PyInstaller) pour se passer de l'installation de Python.
- Réponses via NVDA quand il est actif, à la place de la voix SAPI.
