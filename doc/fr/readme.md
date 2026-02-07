# AbsoluteYoutube

Téléchargeur YouTube puissant pour utilisateurs NVDA

![NVDA Logo](https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico)

**Auteur :** chai chaimee  
**GitHub :** https://github.com/chaichaimee/AbsoluteYoutube

## Description

AbsoluteYoutube est un module complémentaire NVDA avancé permettant de télécharger des vidéos et médias YouTube directement depuis le navigateur aux formats MP3, MP4 ou WAV. Il inclut des systèmes intelligents en arrière-plan pour des téléchargements efficaces et reprenables, découpage vidéo, captures d'écran, copie d'URL courte et gestionnaire complet des échecs – tout accessible avec gestes simples et menus.

## Raccourcis clavier

- **NVDA+Y** – Geste de téléchargement (détection de taps)  
  - Appui simple : Télécharger en MP3  
  - Appui double : Télécharger en MP4  
  - Appui triple : Télécharger en WAV  

- **CTRL+Shift+Y** – Menu contextuel / Dossier  
  - Appui simple : Ouvrir menu contextuel  
  - Appui double : Ouvrir dossier de destination  

- **NVDA+Shift+Y** : Basculer mode playlist  

- **ALT+Windows+Y** : Changer cycliquement qualité MP3 (128 → 192 → 256 → 320 kbps)  

Tous les raccourcis utilisent détection de taps (~0.4 s). Remappez dans NVDA → Gestes d'entrée.

## Fonctionnalités

- **Téléchargement multi-format (MP3 / MP4 / WAV)**  
  Appuyez sur NVDA+Y une, deux ou trois fois pour télécharger la vidéo actuelle dans le format choisi. Supporte vidéos uniques et playlists. En mode playlist crée automatiquement un sous-dossier au nom de la playlist – téléchargements uniques restent séparés.

- **Système intelligent de téléchargement en arrière-plan**  
  - Gestionnaire de file : Téléchargements séquentiels ou concurrence limitée (jusqu'à 4 configurable).  
  - Reprise après redémarrage : Téléchargements interrompus sauvegardés et reprenables automatiquement ou par invite.  
  - Réparation auto : Nettoie fichiers temporaires corrompus.  
  - Ignorer existants : Passe automatiquement les fichiers déjà téléchargés.  
  - Téléchargement multi-parties : Divise en jusqu'à 16 parties pour plus de vitesse (optionnel).  
  Toutes les fonctionnalités dans Paramètres NVDA → AbsoluteYoutube.

- **Découpage de clips vidéo**  
  Sur page YouTube → Menu contextuel (CTRL+Shift+Y appui simple) → Paramètres découpage.  
  Définir début/fin → Choisir MP3 (128–320 kbps), MP4 (H.265) ou WAV → Prévisualiser → Télécharger clip.  
  Enregistré comme "Trimmed Clip 1.mp3", etc.

- **Capture d'instantané**  
  Menu contextuel → Snapshot.  
  Télécharge miniature haute qualité en .jpg complet – idéal pour pochettes.

- **Copier URL courte**  
  Menu contextuel → Copy video Shorten URL.  
  Convertit lien complet en format court et copie instantanément.

- **Gestionnaire de téléchargements échoués**  
  Menu contextuel → Download fail manager.  
  Liste avec titre, durée, URL.  
  Clic droit :  
  - Supprimer sélectionné  
  - Télécharger maintenant  
  - Télécharger tous  
  - Tout effacer  
  Échecs persistants – réessayez quand vous voulez.

- **Mise à jour yt-dlp**  
  Manuel : Paramètres → Update yt-dlp now.  
  Auto : Activer "Auto-update yt-dlp on startup".

**Note**  
Toutes les fonctionnalités configurables dans Paramètres NVDA → AbsoluteYoutube. Raccourcis modifiables dans Gestes d'entrée.