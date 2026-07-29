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

### Le trou de couverture, et sa fermeture (2026-07-29, même jour)

**État initial, tel que mesuré** : le self-test ci-dessus prouvait que
l'OUTIL fonctionne sur ce runner, pas que le thread audio de Tuple est sûr —
un grep repo-wide exécuté dans le CI lui-même ne trouvait `[[clang::nonblocking]]`
dans **aucun** fichier sous `source/` ou `tests/`. Rien n'entrait en contexte
temps réel, donc le sanitizer ne pouvait rien signaler dans le code de Tuple.
Deux manques nommés à l'époque, tous deux traités ci-dessous :

1. **Le point d'entrée n'était pas annoté.**
   `TupleProcessor::processBlock` porte désormais `TUPLE_NONBLOCKING`
   (`source/plugin/RealtimeAnnotations.h`), sur la déclaration ET la
   définition — l'attribut fait partie du TYPE de la fonction, une seule des
   deux ne suffirait pas. La macro n'existe que là où le compilateur
   implémente réellement l'attribut ; ailleurs (MSVC) elle s'efface, sans
   quoi chaque unité de compilation Windows sortirait un
   « unknown attribute ». Un build `-DTUPLE_RTSAN=ON` sur un toolchain qui
   ne l'implémente pas s'arrête sur un `#error` : un binaire RTSan sans
   annotation effective serait vert et vide, pire que pas de RTSan du tout.

2. **`tools/proof_hosts/` était Windows-only, et RTSan est macOS-only.**
   Aucun runner ne pouvait charger le plugin ET le sanitizer en même temps.
   `clap_host_smoke.cpp` a désormais une branche `dlopen`/`dlsym` à côté de
   sa branche `LoadLibrary`/`GetProcAddress`, plus la résolution du bundle
   macOS (`Tuple.clap/Contents/MacOS/<binaire>` — `dlopen` sur le `.clap`
   lui-même échoue, c'est un répertoire). `vst3_host_smoke.cpp` n'utilisait
   en fait aucune API Win32 : il était seulement pris dans le même
   `if(... AND WIN32)` de `CMakeLists.txt`, retiré. Le CLAP smoke appelle
   maintenant un vrai `process()` (un bloc de 512 frames) — sans lui, la
   séquence s'arrêtait à `start_processing` et n'entrait jamais dans
   `processBlock`.

**Découverte réelle en chemin — pourquoi `pluginval` ne peut PAS héberger un
build RTSan.** Le step `pluginval --strictness-level 5 (RTSan build)` était
rouge et l'aurait toujours été. Run **30437655033** :

```
==17045==ERROR: Interceptors are not working. This may be because RealtimeSanitizer
is loaded too late (e.g. via dlopen). Please launch the executable with:
DYLD_INSERT_LIBRARIES=/opt/homebrew/Cellar/llvm/22.1.8/lib/clang/22/lib/darwin/libclang_rt.rtsan_osx_dynamic.dylib
"interceptors not installed" && 0
pluginval received Abort trap: 6, exiting immediately
```

Un hôte pré-compilé n'a pas de runtime sanitizer à lui ; celui-ci n'arrive
qu'au `dlopen` du plugin, après le démarrage du processus, trop tard pour
poser ses intercepteurs. Le contournement que le sanitizer suggère lui-même
(`DYLD_INSERT_LIBRARIES`) n'est pas retenu : dyld l'efface pour les binaires
signés en hardened runtime, donc le résultat du check dépendrait de la façon
dont Tracktion a signé sa release — un check dont le sens dépend de la
signature d'un tiers ne vaut rien. Le step est **retiré**, remplacé par les
deux proof hosts, eux-mêmes compilés avec `-fsanitize=realtime` : le runtime
est alors dans l'image principale dès le lancement, et l'instrumentation du
plugin chargé ensuite se résout sur ce même runtime déjà en place.

**Témoin planté (le check ne peut pas devenir un no-op silencieux).** Un run
RTSan qui passe et un run RTSan qui n'instrumente rien se ressemblent
exactement de l'extérieur. Le CI relance donc le MÊME binaire avec
`TUPLE_RTSAN_SABOTAGE=1`, qui arme un `malloc()` délibéré dans
`processBlock` — code compilé uniquement sous `-DTUPLE_RTSAN=ON`, jamais dans
un build livré. Ce run DOIT avorter avec un rapport RealtimeSanitizer ; s'il
sort 0, le CI échoue en disant que l'annotation n'atteint pas le runtime et
que le run propre ne prouvait rien.

**Moitié statique de l'attribut** : l'analyse function-effects de Clang ne
voit pas à travers la répartition virtuelle, donc les appels dans JUCE
(`AudioPlayHead::getPosition()` et voisins) sortent « non prouvés », ce qui
n'est pas « prouvés dangereux ». Le CI collecte ces diagnostics dans
`proof/rtsan-function-effects-<os>.txt` et les remonte en `::warning::` — le
signal bloquant reste le résultat runtime, pas cette liste.

Windows : skip explicite et journalisé (`::notice::`), jamais silencieux,
conforme à la demande du plan. Le leg Windows compile et exécute quand même
les deux proof hosts (sans sanitizer) — c'est ce qui garde la branche
`_WIN32` de `clap_host_smoke.cpp` vivante maintenant qu'elle a une jumelle
POSIX.

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

**Résolu depuis (2026-07-29), hors Task 7.** Le paragraphe ci-dessus reste tel
qu'il a été mesuré ; ce qui suit est la suite, pas une réécriture. Cause racine
réelle : ni `ParameterAdapter` ni le round-trip XML — les six paramètres
round-trippaient déjà correctement. `TupleProcessor::setStateInformation()`
restaurait les valeurs via `apvts.replaceState()` sans jamais appeler
`updateHostDisplay()`, or le wrapper CLAP de clap-juce-extensions n'émet
`host.paramsRescan(CLAP_PARAM_RESCAN_VALUES)` que depuis son propre
`audioProcessorChanged()`, lequel ne s'exécute qu'en réponse à cet appel. L'hôte
avait donc les bonnes valeurs côté plugin et n'était jamais prévenu de les
relire — d'où le « changed without a rescan request » ci-dessus, à la lettre.
Correctif d'une ligne : `source/plugin/PluginProcessor.cpp`, commit `1248379`.

Mesure, pas prévision — premier run vert sur ce SHA, `30437655033` :
`clap-validator validate` = `success` sur les deux OS, Windows rapportant
`44 tests run, 32 passed, 0 failed, 1 warnings, 11 skipped`, et macOS
`state-reproducibility-basic` / `-binary` / `-buffered` → `PASSED`. Reconfirmé
sur `30467546532`. La phrase « rouge en continu par conception » ci-dessus
n'est donc plus d'actualité pour Step 4 ; elle décrivait la situation tant que
le correctif n'existait pas.

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
