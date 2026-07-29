# Task 1 — preuve de build (2026-07-29)

## Ce qui est vérifié

**Configure (CMake 4.4.0, VS 17 2022 x64), depuis un shell propre :**
```
cmake -B build -G "Visual Studio 17 2022" -A x64
```
JUCE 9.0.0 (tag épinglé) et clap-juce-extensions (SHA épinglé, voir
CMakeLists.txt) récupérés par FetchContent, configuration réussie sans
erreur.

**Build VST3 :**
```
cmake --build build --config Release --target TupleVST_VST3
```
→ `build/TupleVST_artefacts/Release/VST3/Tuple.vst3` (5.8 Mo), aucune erreur.

**Build CLAP :**
```
cmake --build build --config Release --target TupleVST_CLAP
```
→ `build/TupleVST_artefacts/Release/CLAP/Tuple.clap` (5.7 Mo), aucune erreur.

**Points d'entrée exportés (`dumpbin -exports`, via vcvars64.bat) :**
- `Tuple.vst3\...\x86_64-win\Tuple.vst3` exporte `GetPluginFactory`,
  `InitDll`, `ExitDll` — signature standard d'un module VST3.
- `Tuple.clap` exporte `clap_entry` — signature standard d'un module CLAP.

Ces deux exports sont la preuve technique que le binaire est un module de
plugin valide pour son format ; ce n'est pas la preuve qu'un hôte le charge
et l'affiche sans crash.

## Ce qui n'est PAS vérifié

**Le chargement réel dans un DAW (Ableton Live 12 Suite, installé sur cette
machine) n'a pas pu être capturé.** Tentative faite via automation GUI
(computer-use) : Live s'est lancé, j'ai ouvert Préférences > Plug-ins pour
pointer un dossier VST3 personnalisé vers `build/TupleVST_artefacts/Release/
VST3/`. À partir de là, les actions clavier/souris ont commencé à échouer
avec des erreurs répétées d'interruption ("user interrupt"), et un menu
contextuel Explorer est apparu de façon inattendue à un endroit non ciblé —
signe cohérent avec un usage concurrent réel de la souris/clavier de cette
machine pendant la session. Par prudence (ne pas se battre pour le contrôle
d'un input avec un humain présent, risque de casser sa session ou de mal
configurer ses préférences Ableton), j'ai arrêté l'automation sans forcer la
suite ni revenir en arrière sur les Préférences (aucun changement n'a
finalement été appliqué : la dernière tentative de chemin avait échoué avec
"nom de dossier invalide" avant l'arrêt).

**Reste à faire par un humain** : ouvrir Ableton Live (ou tout DAW), ajouter
`C:\dev\tuple-vst\build\TupleVST_artefacts\Release\VST3` comme dossier VST3
personnalisé (Préférences > Plug-ins), rescanner, glisser Tuple sur une
piste MIDI/instrument, confirmer qu'il apparaît et ne crashe pas, et
remplacer ce paragraphe par une capture d'écran réelle.
