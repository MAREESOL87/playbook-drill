# Playbook Drill

Application d'entraînement analytique, sur le modèle d'EA Trainer : drill quotidien chronométré (10 questions, score 100-200) sur les règles du Playbook et les erreurs récurrentes observées en séance, cas guidés hebdomadaires à choix notés, suivi de progression synchronisé et lisible par Claude.

Hébergée sur `drill.eldwin-uk.com`, indépendante des autres projets de la VM (dossier, utilisateur, service et port dédiés : 8789).

## Contenu

| Onglet | Ce qu'il fait |
|---|---|
| Aujourd'hui | Série du jour, streak, point faible courant, rappel des 4 familles à réciter |
| Drill | 10 questions chronométrées, correction immédiate. Sélection adaptative : les catégories faibles reviennent plus, les questions vues récemment moins |
| Cas | Cas guidés en 5 décisions notées 2 / 1 / 0, données révélées après chaque choix, débrief |
| Progression | Réussite par catégorie, historique des scores, résultats des cas, code de synchronisation |

Catégories du drill (une par erreur observée) : familles du Playbook, cadrage, points vs pourcents, fausse alternative, attribut observable vs cause supposée, contenu de l'indicateur, parcimonie, séquençage.

Les données (questions, cas) sont en tête du `<script>` de `public/index.html`. Pour une question, la première option est la bonne réponse (les options sont mélangées à l'affichage). Pour un cas, chaque étape a exactement une option à `s:2`.

## Rythme et engagement

L'app applique, dans leur version utile à l'apprentissage, les techniques du playbook persuasion & influence :

| Technique | Dans l'app |
|---|---|
| Identité (cohérence) | Phrase d'identité affichée en tête de la carte du jour, modifiable dans Progression |
| Intention d'implémentation | Heure de la série + « juste après » une habitude existante ; rappelée chaque jour |
| Engagement choisi | Objectif hebdomadaire fixé par l'utilisateur (3, 4 ou 5 séries), compteur visible |
| Aversion à la perte, sans fragilité | Streak de jours actifs avec un joker par semaine |
| Nouveau départ | Lundi : remise à zéro explicite de la semaine ; après 3 jours ou plus d'arrêt : série courte de 6 questions, sans dette |
| Anti « foutu pour foutu » | À partir du jeudi, deux jours manqués ramènent l'objectif affiché à 3 séries au lieu de 5 |
| Action prescrite | Le plan du jour est écrit (nombre de questions, ratées qui reviennent, catégorie faible), un seul bouton |
| Boucle ouverte | Après la série : les ratées « reviennent demain » ; le cas de la semaine reste affiché tant qu'il n'est pas fait |
| Récupération avant relecture | Récitation des 4 familles avant chaque série, auto-déclarée et journalisée |
| Bilan écrit | Vendredi à dimanche : trois lignes (marché, bloqué, heure de la semaine prochaine), qui alimentent l'intention |
| Redevabilité | La progression, le journal et le bilan sont lus par Claude chaque lundi |

Volontairement absents : badges, récompenses aléatoires, rareté artificielle, notifications culpabilisantes.

## Structure

```
public/            l'app (PWA) : index.html, sw.js, manifest, icônes
server/server.py   API de synchronisation (Python 3, bibliothèque standard), port 8789
deploy/            nginx, Caddy, systemd, scripts d'installation et de mise à jour
data/              créé sur la VM : progress.json, token.txt, sauvegardes quotidiennes (ignoré par git)
```

## Installation sur la VM (première fois)

1. DNS : chez le registrar, ajouter un enregistrement **A** `drill` vers l'IP statique de la VM (la même que `ea.eldwin-uk.com`).
2. Sur la VM :
   ```bash
   sudo git clone https://github.com/MAREESOL87/playbook-drill.git /opt/playbook-drill
   sudo bash /opt/playbook-drill/deploy/install.sh
   ```
   Le script crée l'utilisateur `playbook-drill`, le service systemd (port 8789, sert l'app et l'API), détecte le serveur web en façade et affiche le **code de synchronisation**.
3. Façade web, selon la VM :
   - **Caddy dans Docker** : ajouter au Caddyfile monté dans le conteneur le bloc de `deploy/Caddyfile.snippet` (reverse proxy vers la passerelle du réseau Docker, port 8789), puis `docker exec deploy-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile`. HTTPS automatique.
   - **nginx sur l'hôte** : `deploy/nginx-drill.conf` est installé par le script ; `sudo certbot --nginx -d drill.eldwin-uk.com`.
4. Ouvrir `https://drill.eldwin-uk.com`, onglet Progression, coller le code de synchronisation, Activer. Puis, sur le téléphone : Partager → Sur l'écran d'accueil.

## Mises à jour

Chaque lundi, le dépôt reçoit un nouveau cas et des questions construites sur les erreurs de la semaine. Deux options :

- à la main : `sudo bash /opt/playbook-drill/deploy/update.sh`
- automatique, toutes les heures : `echo '0 * * * * root /opt/playbook-drill/deploy/update.sh >> /var/log/playbook-drill-update.log 2>&1' | sudo tee /etc/cron.d/playbook-drill`

Le service worker recharge l'app à la prochaine ouverture quand `public/sw.js` change de version.

## Lecture de la progression par Claude

`GET https://drill.eldwin-uk.com/api/progress?t=CODE` renvoie le document complet : réussite par catégorie, historique des séries, questions manquées (`misses`), résultats des cas, journal des réponses (`log`). C'est ce que Claude lit au début de chaque séance pour choisir le cas du jour et construire les questions de la semaine.

## Test en local

```bash
python3 server/server.py --static
# puis http://127.0.0.1:8789
```

## Sauvegardes

`server.py` copie `data/progress.json` une fois par jour (`data/progress-AAAA-MM-JJ.json`, 30 jours conservés). Pour restaurer : copier une sauvegarde sur `progress.json` et redémarrer le service.
