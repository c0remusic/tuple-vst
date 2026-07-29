# Task 1 — preuve de build (2026-07-29, révisée après revue adverse)

## Ce qui est vérifié

**Configure (CMake 4.4.0, VS 17 2022 x64), depuis un dossier vierge :**
```
cmake -B build-verify-clean -G "Visual Studio 17 2022" -A x64
```
JUCE 9.0.0 (tag épinglé) et clap-juce-extensions (SHA épinglé, voir
CMakeLists.txt) récupérés par FetchContent, configuration réussie sans
erreur (67 s, réseau inclus).

**Build VST3 et CLAP, depuis ce même dossier vierge :**
```
cmake --build build-verify-clean --config Release --target TupleVST_VST3
cmake --build build-verify-clean --config Release --target TupleVST_CLAP
```
→ `Tuple.vst3` et `Tuple.clap`, aucune erreur.

**Points d'entrée exportés (`dumpbin -exports`, via vcvars64.bat) :**
- `Tuple.vst3\...\x86_64-win\Tuple.vst3` exporte `GetPluginFactory`,
  `InitDll`, `ExitDll`.
- `Tuple.clap` exporte `clap_entry`.

## Chargement réel dans un hôte — Step 5

**Le chargement dans une GUI DAW (Ableton Live) n'a pas été retenté.** La
première tentative (automation GUI via computer-use) avait montré des signes
clairs d'un usage concurrent réel du clavier/souris de cette machine pendant
la session ; forcer une seconde tentative reprendrait le même risque
d'interférer avec une session humaine en cours sur une machine partagée. Ce
choix est documenté ici plutôt que retenté à l'aveugle.

**À la place, Step 5 est vérifié par deux hôtes minimaux mais réels**,
ajoutés sous `tools/proof_hosts/` (hors du build du plugin — jamais lié dans
le `.vst3`/`.clap` livré) :

- `tools/proof_hosts/vst3_host_smoke.cpp` — charge `Tuple.vst3` via
  `juce::VST3PluginFormat`/`AudioPluginFormatManager`, le même code d'hébergement
  que n'importe quel hôte basé sur JUCE (ex. Tracktion Waveform). Instancie
  réellement le plugin via sa factory VST3, puis
  `prepareToPlay` → `processBlock` → `releaseResources` → destruction.
- `tools/proof_hosts/clap_host_smoke.cpp` — charge `Tuple.clap` via l'ABI C
  CLAP brute (`clap_entry` → `get_factory` → `create_plugin` → `init` →
  `activate` → `start_processing` → `stop_processing` → `deactivate` →
  `destroy` → `deinit`), la même séquence que tout hôte CLAP.

Les deux sont construits et exécutés depuis le dossier vierge ci-dessus,
contre les binaires fraîchement compilés dans ce même dossier :

```
cmake --build build-verify-clean --config Release --target TupleVST3HostSmoke
cmake --build build-verify-clean --config Release --target TupleClapHostSmoke

TupleVST3HostSmoke_artefacts/Release/TupleVST3HostSmoke.exe Tuple.vst3
  OK: instantiated "Tuple" via VST3PluginFormat, 0 in / 2 out, 2081 parameters
  OK: prepareToPlay -> processBlock -> releaseResources -> destroyed, no crash
  EXIT=0

Release/TupleClapHostSmoke.exe Tuple.clap
  OK: factory describes "Tuple" (id=live.tuple.chords)
  OK: init -> activate -> start_processing -> stop_processing -> deactivate -> destroy -> deinit, no crash
  EXIT=0
```

(2081 paramètres VST3 : comportement JUCE par défaut pour un synthé MIDI
sans paramètres exposés — un paramètre par CC MIDI générique, pour
l'automation générique côté hôte. Tuple n'a pas encore ses 6 paramètres réels
— Task 4.)

**Ce que ça prouve** : la factory du module est appelée, le plugin
s'instancie, tourne un cycle audio complet et se détruit proprement, sur les
deux formats — pas seulement « le DLL exporte le bon nom de symbole »
(`dumpbin`), mais « la séquence d'appels qu'un hôte fait réellement ne
crashe pas ».

**Ce que ça ne prouve toujours pas** : que le scanner et l'UI propres
d'Ableton Live acceptent le plugin, ni que son éditeur s'ouvre correctement à
l'écran dans une vraie session DAW. Cette part reste à faire par Antoine
(ou dans une session où l'automation GUI n'entre pas en conflit avec un usage
concurrent de la machine) : ajouter
`build/TupleVST_artefacts/Release/VST3` comme dossier VST3 personnalisé
(Préférences > Plug-ins), rescanner, glisser Tuple sur une piste
MIDI/instrument, confirmer qu'il apparaît et ne crashe pas, capture d'écran à
l'appui.
