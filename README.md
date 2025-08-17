# Miri — IA d’accueil (Discord.py + OpenAI)

Bot de bienvenue **Miri** pour le serveur Miri :
- Souhaite la bienvenue dans <#1400520326130962476>.
- ~40% du temps, ajoute une redirection ticket **GS** (<#1400520220560457799>) ou **Recrutement** (<#1400520224721076406>).
- Répond via IA quand on la **mentionne** ou qu’on **répond à ses messages** (ton normal / piquant / recadrage si provocation).
- **Mémoire persistante** (SQLite) par membre (notes, stats).
- **Banter auto** (vannes soft-trash) sur membres actifs, **sans ping** par défaut.
- **Ping contrôlé**:
  - Ping-banter **exceptionnel** automatique seulement si **salon calme** + **cooldowns**.
  - Commande `/miri_ping` **réservée à la whitelist (users/roles)**.

## Déploiement (Railway)
1. Crée un repo GitHub avec ces fichiers.
2. Railway → **New Project** → **Deploy from GitHub**.
3. Dans **Variables**, copie le contenu de `.env.example` et remplis.
4. Dans Discord Developer Portal → **Bot**:
   - Active **Server Members Intent** et **Message Content Intent**.
5. Invite le bot avec permissions de base (Send Messages, Embed Links, Use Application Commands).
