# learning-log — tuple-vst

Leçons durables propres à ce dépôt. Lecteur = hook SessionStart. Écrivain =
`wrap-up` seul. Les leçons de méthode globales vivent dans
`~/.claude/instinct-log.md`.

---

## Découvertes — 2026-07-29 (TTL 6 mois)

### RealtimeSanitizer ne peut pas instrumenter un plugin chargé par l'hôte
`-fsanitize=realtime` installe ses interceptors **au lancement du processus**.
Un plugin est chargé par `dlopen` — c'est sa définition — donc les interceptors
n'existent jamais. Message exact observé en CI :
`ERROR: Interceptors are not working. This may be because RealtimeSanitizer is
loaded too late (e.g. via dlopen).`
→ **La preuve des invariants du thread audio doit vivre sur le binaire de test**,
pas sur le plugin hébergé. Le plan de phase 0 demandait l'inverse : c'était une
erreur de conception, pas un bug d'implémentation.

### `-fsanitize=realtime` n'est accepté que par le LLVM de Homebrew
Vérifié par sonde jetable en CI réelle, pas supposé :
- `clang-cl 20.1.8` (le LLVM du runner `windows-latest`) le **rejette** pour la
  cible `x86_64-pc-windows-msvc` : *unsupported option*.
- Le clang d'Apple embarqué dans Xcode 26.5 le **rejette** aussi.
→ Windows ne peut pas faire tourner RTSan du tout. Le skip doit être **journalisé
explicitement**, jamais silencieux.

### Un test maison peut passer pendant que le produit est cassé
`tests/params_tests.cpp` vérifiait « sauvegarder → recharger → six valeurs
identiques » et il était **vert**. `clap-validator` a trouvé le bug quand même :
après *randomiser → sauvegarder → recréer → recharger*, cinq paramètres
revenaient différents. Cause racine : le plugin rechargeait son état mais **ne
notifiait pas l'hôte**, qui gardait ses valeurs en cache (corrigé par `1248379`).
→ Le test maison ne randomisait pas et ne traversait pas le vrai chemin d'état de
l'hôte. **Un validateur externe couvre ce qu'un test écrit par l'auteur du code
ne voit pas.** C'est la raison d'être de `clap-validator` dans la CI, et elle
s'est vérifiée dès le premier run.

### L'asset macOS de clap-validator contient une archive imbriquée
Le `.zip` `...-0.4.1-...-macos-universal.zip` contient un `.tar.gz` dont le nom
porte **une version différente** (`0.3.2`). Un script qui cherche l'exécutable
directement dans le zip ne le trouve pas. `ci.yml` dépile toute archive imbriquée
avant de chercher le binaire.

### Un échec de pas non gardé masque tous les contrôles suivants
Sans `if: always()` (ou équivalent) sur chaque contrôle indépendant, l'échec d'un
pas fait sauter en cascade les suivants — le job ne produit plus **aucun signal**
sur des contrôles qui marchaient. Observé en réel : un échec RTSan a masqué le
build des formats, `clap-validator` et `pluginval` d'un coup.
→ Chaque contrôle indépendant rapporte son propre verdict. Le job échoue
globalement, mais on sait lesquels.

---

## Convention — ne pas « corriger »

`register` est un **mot réservé en C++**. L'identifiant de paramètre exposé au
DAW est bien la chaîne `register`, mais le champ C++ correspondant s'appelle
`centre` partout. Cette différence est délibérée. Renommer l'identifiant exposé
casserait les projets sauvegardés des utilisateurs.
