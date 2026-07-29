# Task 7 — preuve de validation automatisée (2026-07-29)

Toutes les affirmations ci-dessous sont vérifiées sur des runs GitHub Actions
réels (`gh run view`, logs bruts récupérés via `gh api .../logs`), pas
déduites. IDs de run cités pour audit ultérieur (`gh run view <id>`).

## Step 1 — matrice deux OS

`strategy.matrix.os: [windows-latest, macos-latest]`, un seul workflow
(`.github/workflows/ci.yml`), un seul job `build-and-validate`.

Run de référence final : **30430181564**
(https://github.com/c0remusic/tuple-vst/actions/runs/30430181564)
— les deux legs verts sauf `clap-validator validate` (bug réel, voir Step 4).

## Step 2 — binaire de test (bloquant)

Build + exécution de `DomainTests`, `VoicingTests`, `GridTests`,
`NoteoffTests`, `ParamsTests` sur les deux OS. Les cinq passent réellement
(logs : `All domain tests passed.`, `All voicing tests passed.`, etc., sur
Windows ET macOS, run 30426793856).

## Step 3 — RealtimeSanitizer

**Fait vérifié, pas une hypothèse** (probe throwaway, supprimée) : `-fsanitize=realtime` est
**rejeté** par :
- clang-cl 20.1.8 (le LLVM déjà sur le PATH de `windows-latest`) pour la cible
  `x86_64-pc-windows-msvc` : `clang-cl: error: unsupported option
  '-fsanitize=realtime' for target 'x86_64-pc-windows-msvc'`.
- le clang Apple embarqué (Xcode 26.5, `arm64-apple-darwin25.4.0`) :
  `clang++: error: unsupported option '-fsanitize=realtime' for target
  'arm64-apple-darwin25.4.0'`.

Il **fonctionne** avec un LLVM/clang générique installé via Homebrew sur
macOS (`brew install llvm` → clang 22.1.8) : une fonction jetable annotée
`[[clang::nonblocking]]` qui appelle `malloc()` avorte réellement :

```
==3856==ERROR: RealtimeSanitizer: unsafe-library-call
Intercepted call to real-time unsafe function `malloc` in real-time context!
    #0 ... in malloc+0x20 (libclang_rt.rtsan_osx_dynamic.dylib:arm64+0x3524)
    #1 ... in violatesRealtime()+0x14
SUMMARY: RealtimeSanitizer: unsafe-library-call ... in violatesRealtime()+0x14
```

et la même fonction sans allocation sort proprement (exit 0). C'est exactement
ce que `ci.yml` fait à chaque run macOS (step "RTSan self-test"), donc CETTE
preuve n'est pas un one-off : elle se réexécute et doit continuer à réussir à
chaque push, sinon la sanitizer lui-même serait suspect (voir sa clause
`::error::` en cas d'échec).

⚠️ **Point non résolu, dit explicitement dans les logs ET ici, pas balayé
sous le tapis** : au 2026-07-29, **aucun fichier** sous `source/` ou `tests/`
ne porte l'annotation `[[clang::nonblocking]]` (grep repo-wide confirmé dans
le CI lui-même à chaque run, step "RTSan coverage gap"). Le self-test prouve
que l'OUTIL fonctionne sur ce runner ; il ne prouve PAS que le thread audio de
Tuple est sûr, puisque rien n'entre encore en "contexte temps réel" du point
de vue du sanitizer. Pour que Step 3 devienne une vraie preuve de couverture,
il manque :
1. Annoter le vrai point d'entrée (`TupleProcessor::processBlock`) —
   hors périmètre de cette tâche (Files = `.github/workflows/ci.yml`
   seulement, et Task 5 est déjà committée).
2. `tools/proof_hosts/` est actuellement **Windows-only**
   (`vst3_host_smoke.cpp`/`clap_host_smoke.cpp` utilisent `LoadLibrary`/
   `GetProcAddress`) alors que RTSan ne tourne que sur macOS — aucun runner
   ne peut aujourd'hui charger le plugin ET le sanitizer en même temps. Il
   faudrait porter ces hôtes en `dlopen`/`dlsym` (déjà noté comme travail
   restant dans `proof/task1-build.md`).

Windows : skip explicite et journalisé (`::notice::`), jamais silencieux,
conforme à la demande du plan.

## Step 4 — clap-validator

`clap-validator validate build/TupleVST_artefacts/Release/CLAP/Tuple.clap`,
binaire téléchargé depuis la release GitHub la plus récente de
`free-audio/clap-validator` (asset détecté par suffixe `-windows.zip` /
`-macos-universal.zip`).

⚠️ **Piège d'extraction découvert en CI réelle** (pas documenté en amont) :
l'asset `.zip` de macOS contient un **`.tar.gz` imbriqué** dont le nom de
version diffère de celui du zip externe
(`clap-validator-0.3.2-...-macos-universal.tar.gz` dans un zip nommé
`...-0.4.1-...`). `ci.yml` détecte et dépile toute archive imbriquée avant de
chercher l'exécutable.

**Résultat réel, les deux OS (runs 30428944306 macOS, même run côté Windows)** :
3 tests échouent, à l'identique sur Windows et macOS —

```
ERROR Test state-reproducibility-basic failed
ERROR Test state-reproducibility-binary failed
ERROR Test state-reproducibility-buffered failed
```

Détail (`state-reproducibility-basic`) : après un cycle randomize → save →
recreate → reload, ces paramètres reviennent avec une valeur différente sans
demande de rescan : `Key`, `Scale`, `Density`, `Register`, `Openness`.

**C'est un bug réel dans le code déjà committé (Task 4, `ParameterAdapter`
et/ou le wrapper CLAP), pas un artefact de CI.** Hors périmètre de cette
tâche (Files = `.github/workflows/ci.yml` uniquement ; Task 4 est déjà
committée, je ne la refais pas) — signalé ici et via `spawn_task` pour une
session dédiée. Tant qu'il n'est pas corrigé, **ce job CI est rouge en
continu par conception** (Step 4 est explicitement bloquant dans le plan) —
ce n'est pas une régression de Task 7, c'est Task 7 qui le révèle pour la
première fois.

Sortie complète archivée en artefact CI (`proof-<os>`,
`clap-validator-<os>.txt`) à chaque run, pas committée dans le dépôt (un
commit automatique par push aurait pollué l'historique — voir note de portée
plus bas).

## Step 5 — pluginval --strictness-level 5

`pluginval --strictness-level 5 --validate build/TupleVST_artefacts/Release/VST3/Tuple.vst3`,
binaire téléchargé depuis la release GitHub la plus récente de
`Tracktion/pluginval`.

**Résultat réel, les deux OS (run 30430181564)** : `SUCCESS` — toutes les
catégories (Open plugin, Editor, Audio processing, Plugin state, Automation,
Editor Automation, vst3 validator, bus layout, ...) passent, exit code 0 sur
Windows et macOS. Contrat exit-code 0/1 respecté (aucun crash/segfault
observé).

Sortie archivée en artefact CI (`pluginval-<os>.txt`).

## Step 6 — la CI peut rejeter (preuve, pas affirmation)

Branche jetable `task7-step6-sabotage-throwaway`, un seul commit :
`source/app/ReleaseAll.cpp`, boucle d'émission des note-off changée de
`i < sounding.count` à `i < 0` (note-offs retirés).

**Vérifié en LOCAL d'abord** (`NoteoffTests.exe` recompilé, Release,
MSVC) : 9 échecs, dont les quatre déclencheurs du contrat note-off :

```
[FAIL] Trigger 1 (changement d'accord): every note-on across two chord changes gets exactly one note-off
[FAIL] Trigger 2 (arret du transport): releaseAll() on transport stop clears every sounding note-on
[FAIL] Trigger 3 (releaseResources): releaseAll() clears every sounding note-on
[FAIL] Trigger 4 (destruction du plugin): releaseAll() clears every sounding note-on
9 note-off test(s) FAILED.
```

**Puis vérifié sur la vraie CI** (run **30429637034**,
https://github.com/c0remusic/tuple-vst/actions/runs/30429637034) : les deux
OS rejettent la branche au step "run fast test binaires" (Step 2), avec la
sortie **identique** (mêmes 9 `[FAIL]`, même total). Le job s'arrête net —
Steps 3 à 5 sont proprement `skipped`, pas exécutés sur du code cassé.

Branche supprimée après capture (`git push origin --delete
task7-step6-sabotage-throwaway` + suppression locale) — plus nulle part sur
le remote ni en local.

## Aparté — l'image `windows-latest` a changé de version de Visual Studio

Découvert en cours de route, pas une supposition : au 2026-07-29,
`windows-latest` installe **Visual Studio 18/2026 (Enterprise)**, pas VS
17/2022. Un `cmake -G "Visual Studio 17 2022"` échoue avec « could not find
any instance of Visual Studio » — `ci.yml` laisse donc CMake choisir son
générateur par défaut (`cmake -B build -A x64`, sans `-G`) plutôt que de
figer une version liée à la date d'écriture de ce fichier.

## Décision — `TUPLE_BUILD_PROOF_HOSTS`

Passé à `OFF` pour la CI (`-DTUPLE_BUILD_PROOF_HOSTS=OFF` à la configure),
comme suggéré par la revue de la Task 1. Raisons :
1. Ces cibles (`TupleVST3HostSmoke`, `TupleClapHostSmoke`) sont **Windows-only**
   (`if(... AND WIN32)`), donc n'apportent rien à la moitié macOS de la
   matrice.
2. Leur rôle (« charge dans un hôte réel, ne crashe pas ») est **strictement
   subsumé** par Steps 4/5 : `clap-validator` et `pluginval` sont des
   validateurs dédiés, bien plus stricts, qui font déjà ce chargement réel
   pour les deux formats.
3. Les construire ajoute du temps de build réel (linkage de modules JUCE hôte
   supplémentaires) pour zéro couverture CI additionnelle.
Elles restent utiles en développement local (preuve manuelle Task 1,
`proof/task1-build.md`) — seul le défaut CI change.

## Portée — ce que `proof/` contient vs ce que la CI archive

Ce fichier documente la preuve one-shot de mise en place de Task 7. La sortie
brute de CHAQUE run (clap-validator, pluginval) est archivée comme artefact
CI téléchargeable (`proof-windows-latest`, `proof-macos-latest`), pas
committée dans `proof/` à chaque push — un commit automatique par run aurait
pollué l'historique git pour une donnée qui n'a de valeur que jusqu'au run
suivant.

## Suivi hors périmètre (à ouvrir en tâches séparées)

1. **Bug réel** : `state-reproducibility-{basic,binary,buffered}` échoue sur
   les deux OS (Step 4). À investiguer côté `ParameterAdapter`/wrapper CLAP.
2. **Couverture RTSan nulle** : aucune annotation `[[clang::nonblocking]]`
   dans `source/`. Nécessite (a) annoter `processBlock`, (b) porter
   `tools/proof_hosts/` en `dlopen`/`dlsym` pour qu'un hôte macOS existe.
