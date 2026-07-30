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

**RÉFUTÉ EN PARTIE le 2026-07-30 (même mécanisme, conclusion trop large).** Le
mécanisme décrit ci-dessus est exact ; la conclusion « donc jamais via un hôte »
ne l'est pas. Ce qui compte n'est pas que le plugin arrive par `dlopen`, c'est
que le **runtime sanitizer soit dans l'image principale au lancement**. Un hôte
que NOUS compilons avec `-fsanitize=realtime` satisfait ça : ses interceptors
sont posés avant tout chargement, et l'instrumentation du plugin chargé ensuite
se résout sur ce même runtime déjà en place. Mesuré, run **30471091956** — le
sanitizer nomme notre propre symbole depuis un hôte :
```
SUMMARY: RealtimeSanitizer: unsafe-library-call (Tuple:arm64+0x22c4c)
  in TupleProcessor::processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&)+0x3c
```
Ce qui reste vrai : un hôte **pré-compilé** (pluginval, un DAW) ne peut pas le
faire, faute de runtime à lui. La distinction utile est donc
« hôte instrumenté ou non », pas « hôte ou binaire de test ».

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

## Découvertes — 2026-07-29, suite (TTL 6 mois)

### Un job à `0 step` avec `runner_name` vide n'est pas un échec, c'est une machine jamais allouée
Signature observée trois fois de suite sur `phase-0` (runs 30472594056, son
re-run, puis 30473939719) : `conclusion: failure`, **0 step**, `runner_name: ""`,
durée de vie 4 à 15 s, et le blob de log rend `BlobNotFound` (HTTP 404). Le
workflow est valide — les jobs sont bien CRÉÉS, et le YAML du commit incriminé
parse sans erreur ; ils n'obtiennent simplement jamais de runner. Cause probable
non confirmée (l'API de facturation exige le scope `user`) : quota de minutes
Actions épuisé sur ce dépôt **privé**.
→ **Contrôle qui distingue les deux cas en une commande** : comparer à un run
voisin via `gh api repos/<o>/<r>/actions/runs/<id>/jobs -q '.jobs[] | "\(.steps|length) steps | runner=\"\(.runner_name)\""'`.
Un vrai échec rend `27 steps`. Ne pas partir en debug du code sur un `0 step` :
il n'y a rien à déboguer, le job n'a pas tourné. Un re-run ne prouve rien non
plus dans ce cas — il rend la même chose.

### Un push sur ce dépôt coûte de l'ordre de 150 minutes de quota facturées
Mesuré sur les runs 30467546532 / 30469650838 / 30471091956 : Windows 20 à
24 min réelles, macOS 7 à 13 min. Aux multiplicateurs GitHub (Windows ×2,
macOS ×10), macOS est le poste dominant (~110 min) devant Windows (~45 min).
Sur un dépôt privé, une journée d'itérations CI épuise un quota mensuel.
→ Deux gaspillages corrigés dans `ci.yml` (commit `51b4e57`), avec leur
contrepartie écrite dans le fichier : `paths-ignore` sur `**.md` et `proof/**`,
et un bloc `concurrency` à `cancel-in-progress`. Avant ça, `on: push:` était nu :
trois runs ont tourné en parallèle sur la même branche, dont deux déjà périmés.

---

## Convention — ne pas « corriger »

`register` est un **mot réservé en C++**. L'identifiant de paramètre exposé au
DAW est bien la chaîne `register`, mais le champ C++ correspondant s'appelle
`centre` partout. Cette différence est délibérée. Renommer l'identifiant exposé
casserait les projets sauvegardés des utilisateurs.
