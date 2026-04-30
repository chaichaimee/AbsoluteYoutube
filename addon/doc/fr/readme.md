<div align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="Logo NVDA" width="120">
  <h1>AbsoluteYoutube</h1>
  <br>
  <p>Puissant téléchargeur YouTube pour les utilisateurs de NVDA</p>
</div>

<br>

<div align="center">
  <p><b>auteur :</b> chai chaimee</p>
  <p><b>url :</b> https://github.com/chaichaimee/AbsoluteYoutube</p>
</div>

---
<br>

> ## Quoi de neuf : La mise à jour Unbound
> **Boostez votre flux de travail : Téléchargements de liens directs !**
>
> Pourquoi perdre du temps à ouvrir une page vidéo quand vous pouvez l'obtenir instantanément ? Notre dernière mise à jour introduit la fonction révolutionnaire **"Focus & Fetch"**. Il suffit de placer votre curseur sur n'importe quel lien vidéo et de lancer votre téléchargement immédiatement — plus besoin d'attendre le chargement des pages !
>
> • **Unbound Search :** Découvrez plus de contenu que jamais. Notre nouveau moteur contourne les limites standard de l'algorithme YouTube, trouvant des vidéos souvent cachées dans les recherches habituelles.
>
> • **Gestionnaire de chaînes favorites :** Créez votre propre collection de créateurs et recevez des mises à jour automatiques sur les derniers contenus.
>
> • **Contrôle intelligent de la file d'attente :** Gérez vos téléchargements efficacement avec le nouveau système de file d'attente en arrière-plan.

<br>

## Description
AbsoluteYoutube est une extension NVDA avancée qui vous permet de télécharger des vidéos et des médias YouTube aux formats MP3, MP4 ou WAV directement depuis votre navigateur. Elle comprend des systèmes intelligents en arrière-plan pour des téléchargements efficaces et reprenables, le découpage vidéo, des captures d'écran, la copie d'URL courtes et un gestionnaire complet de téléchargements échoués – le tout accessible avec des gestes et des menus simples.

<br>

## Touches de raccourci
**NVDA+Y** – Commande de téléchargement (Détection multi-frappe)  
• Appui simple : Télécharger en MP3 (Haute qualité)  
• Appui double : Télécharger en MP4 (Vidéo)  
• Appui triple : Télécharger en WAV (Audio non compressé)

**CTRL+Maj+Y** – Options & Outils  
• Appui simple : Ouvrir le menu contextuel (Accès à tous les outils)  
• Appui double : Ouvrir le dossier de destination des téléchargements  
• **Appui triple : Ouvrir la nouvelle boîte de dialogue de recherche** (Accès aux résultats Unbound Search)

**NVDA+Ctrl+Y** – Basculer le téléchargement automatique  
• Basculer entre le téléchargement instantané et le **Mode file d'attente**. Lorsqu'il est désactivé, les liens sont envoyés au Gestionnaire de liste de téléchargement pour une action ultérieure.

**NVDA+Maj+Y** : Activer/désactiver le mode playlist

**ALT+Windows+Y** : Faire défiler la qualité MP3 (128 → 192 → 256 → 320 kbps)

> Tous les raccourcis utilisent la détection de frappe (fenêtre de temps ~0,4 seconde). Vous pouvez les réattribuer dans NVDA → Gestes de commande.

<br>

## Explication des fonctionnalités clés
* **1. Dialogue Unbound Search (Triple appui Maj+Ctrl+Y)**  
  Ce n'est pas une recherche standard. En déclenchant le triple appui, vous entrez dans une interface de recherche spécialisée. Contrairement au site YouTube qui limite les résultats en fonction de votre historique, cet outil récupère des données brutes, vous donnant accès à une plus grande variété de vidéos et d'informations.

<br>

* **2. Collection de chaînes favorites (Guide étape par étape)**  
  Ne perdez jamais de vue vos créateurs préférés. Voici comment construire votre collection :  
  * **Étape 1 :** Allez sur YouTube et copiez l'URL de la chaîne que vous souhaitez suivre (ex: youtube.com/@NomDeLaChaine).
  * **Étape 2 :** Ouvrez le menu contextuel d'AbsoluteYoutube (Appui simple Ctrl+Maj+Y) et sélectionnez "Chaînes favorites".
  * **Étape 3 :** Sélectionnez l'option pour ajouter une nouvelle chaîne et collez l'URL copiée.
  * **L'avantage :** Une fois ajoutée, chaque fois que vous ouvrez cette chaîne via le dialogue, le système vérifie automatiquement les nouveaux ajouts de vidéos et vous les présente instantanément dans une liste.

<br>

* **3. Gestionnaire de liste de téléchargement & file d'attente (NVDA+Ctrl+Y)**  
  Si vous êtes occupé et ne voulez pas télécharger immédiatement, appuyez sur **NVDA+Ctrl+Y** pour désactiver le téléchargement automatique. Tous vos fichiers demandés seront envoyés dans une "file d'attente".  
  • Pour les traiter, ouvrez le **Gestionnaire de liste de téléchargement** depuis le menu contextuel.  
  • Faites un clic droit sur n'importe quel élément pour démarrer le téléchargement, le supprimer ou réessayer.

<br>

* **4. Système de téléchargement intelligent en arrière-plan**  
  • Gestionnaire de file d'attente : Les téléchargements s'exécutent un par un pour économiser le processeur/RAM.  
  • Reprise au redémarrage : Les téléchargements interrompus sont sauvegardés et reprennent automatiquement au redémarrage de NVDA.  
  • Réparation auto des fichiers : Nettoie les fichiers temporaires corrompus avant de commencer.  
  • Ignorer l'existant : Empêche de télécharger deux fois le même fichier.

<br>

* **5. Découpage de clips vidéo (uTubeTrim)**  
  Ouvrir le menu contextuel → Paramètre de découpage. Définissez l'heure de début/fin et choisissez votre format. Parfait pour récupérer des segments spécifiques sans télécharger toute la vidéo.

<br>

* **6. Gestionnaire d'échecs de téléchargement**  
  Liste persistante des éléments ayant échoué. Clic droit sur n'importe quel élément pour réessayer, effacer ou télécharger toutes les tâches restantes.

<br>

> **Note :** Toutes les fonctionnalités sont hautement configurables dans Paramètres NVDA → Absolute YouTube. Les raccourcis peuvent être modifiés dans Gestes de commande.

<br>
<br>

## Me soutenir
Si cet outil a facilité votre vie, envisagez de soutenir la prochaine mise à jour par un petit don.

<br>

[![Soutenez-moi](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/dRm9AU1xQ3Ds22N6VK1VK01)

<br>

Votre soutien compte énormément. Construisons quelque chose de génial ensemble.

<br>

&copy; 2026 Chai Chaimee Extension NVDA publiée sous GNU