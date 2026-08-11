# Tuple VST

Plugin d'accords **MIDI-only** pour DAW, en VST3 et CLAP. Produit **commercial
sous licence propriétaire** (`LICENSE` : all rights reserved), distinct de Tuple
(le device Max for Live, qui reste MIT et gratuit). Le dépôt est **public et le
reste** : source-available, pas open source — la licence est fermée, pas la
visibilité. Deux développeurs : Antoine sous Windows, Stéphane sous macOS.

Le QUOI vit dans `PRD.md`. Le COMMENT dans `ARCHITECTURE.md`. Le plan courant
dans `docs/plans/`. Ce fichier ne porte que les invariants — ce qu'on ne peut
pas casser sans casser le produit.

---

## Ce qui est définitif

Ces valeurs sont figées **à vie** : les changer après la première vente casse
les projets sauvegardés des utilisateurs.

**Identifiants du plugin**

```
Nom du fabricant   Tuple
Code fabricant     Tupl
Nom du plugin      Tuple
Code plugin        Chrd
Identifiant CLAP   live.tuple.chords
Bundle macOS       live.tuple.chords
```

**Les six paramètres automatisables**, et il n'y en a pas d'autres :
`key`, `scale`, `octave`, `openness`, `density`, `register`.

⚠️ **`register` est un mot réservé en C++.** L'identifiant exposé au DAW est bien
la chaîne `register`, mais le champ C++ s'appelle **`centre`** partout dans le
code. Ce n'est pas une faute à corriger.

**L'accord joué n'est PAS un paramètre.** Il ne s'automatise pas depuis la
timeline. La grille se joue à la souris ou par note MIDI entrante.

**Les six familles de voicing** : `Close`, `Open`, `Drop`, `Rootless`,
`Quartal`, `TwoHand`. Il n'y a **pas** de catalogue de 28 types — c'était le
device Max for Live, et les noms évoquant un genre musical ont disparu.

---

## Les trois couches, et la règle qui les tient

```
source/domain/   règles harmoniques pures — ChordSpec, Voicing, Scale, Key
source/app/      cas d'usage — BuildGrid, PlayChord, ReleaseAll, TransportStop
source/plugin/   JUCE, adaptateurs compris — Processor, Editor, MidiEmitter
```

**Rien sous `domain/` ni `app/` n'inclut un en-tête JUCE.** C'est la seule règle de
structure, et elle se vérifie mécaniquement :

```bash
grep -rniE '#\s*include\s*[<"][^>"]*juce' source/domain/ source/app/
```

Elle doit ne rien retourner. C'est ce qui permet au binaire de test de démarrer
en une seconde, sans hôte audio — et donc de tester la logique métier en boucle
courte.

---

## Invariants du thread audio

Non négociables. Le troisième est une promesse produit.

1. **Zéro allocation, zéro lock, zéro I/O, zéro exception** dans `processBlock`
   et tout ce qu'il appelle. Buffers de taille fixe alloués dans `prepareToPlay`.
2. Les cas d'usage retournent des **structures de valeur de taille fixe**, sur la
   pile. Jamais de `std::vector`, `std::string`, `std::function` ni de `new` en
   retour. L'appel virtuel coûte quelques nanosecondes et ne pose aucun problème ;
   c'est l'allocation qui glitche.
3. **Toute note-on a exactement une note-off**, sur les quatre déclencheurs :
   changement d'accord, arrêt du transport, `releaseResources`, destruction du
   plugin. C'est le bug que le concurrent traîne depuis 2020 ; c'est notre
   argument. Les quatre sont testés au niveau des fonctions pures dans
   `tests/noteoff_tests.cpp`. Le déclencheur « changement d'accord » n'est PAS
   encore exercé de bout en bout : `playChord` n'a aucun appelant dans
   `source/plugin/` tant que Trigger 1 n'est pas câblé (vérifié 2026-07-30).
4. Les notes sont placées à leur **offset d'échantillon exact**
   (`addEvent(msg, sampleOffset)`), jamais à 0.

---

## Licence — discipline, il n'existe aucun garde-fou automatique

Le produit est fermé et commercial. **Aucune dépendance copyleft, même
transitive.**

- **Épingler la version de JUCE** dans le CMake. Jamais de branche flottante.
- **Ne jamais activer AAX ni ASIO** — SDK propriétaires ou GPLv3.
- Laisser `JUCE_USE_MP3AUDIOFORMAT` et `JUCE_WEB_BROWSER` à `0`.
- Toute dépendance ajoutée : licence vérifiée et **notée dans la PR**.
  Acceptables : MIT, Apache-2.0, ISC, BSD-2, BSD-3, plus la licence commerciale
  JUCE.

Détail des tiers JUCE et de leurs plafonds : `ARCHITECTURE.md` §3. Le plafond
porte sur le revenu de l'entité entière, pas sur les ventes du plugin.

---

## Construire et tester

L'outillage est installé mais **hors du `PATH` du shell** :

```bash
export PATH="$PATH:/c/Program Files/CMake/bin"
```

MSVC passe par `vcvars64.bat`, sous
`C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/`.

⚠️ **Git Bash mange les arguments `/flag` de MSVC.** Utiliser la forme `-flag` :
`dumpbin -exports`, jamais `dumpbin /exports`.

Cibles de test, toutes sans JUCE sauf `ParamsTests` :

```
DomainTests   VoicingTests   GridTests   ParamsTests   NoteoffTests
```

`build/` est ignoré par git et pèse près d'un gigaoctet — JUCE y est récupéré par
CMake. Ne jamais le committer.

---

## Ce que la CI vérifie, et pourquoi

Matrice **Windows et macOS**, les deux dès le premier jour.

- Les cinq binaires de test, bloquants.
- **`clap-validator`** sur le `.clap` — le seul validateur dont la couverture
  note on/off et événements MIDI est documentée. Il a trouvé un vrai bug de
  persistance que nos propres tests, verts, n'avaient pas vu.
- **`pluginval --strictness-level 5`** sur le `.vst3`.

**Chaque contrôle rapporte son propre verdict.** Un pas qui échoue ne doit jamais
masquer les suivants — c'est arrivé, et le job ne produisait plus aucun signal.

---

## Propriété des fichiers

Aucun mécanisme de verrouillage n'existe entre sessions ou entre agents : la
seule protection est la disjonction déclarée à l'avance.

| zone | propriétaire |
|---|---|
| `source/domain/`, `source/app/`, `fixtures/`, `tests/`, `tools/blender/` | Antoine |
| `source/plugin/PluginEditor.*`, `tools/proof_hosts/`, CI | Stéphane |
| `CMakeLists.txt`, `ARCHITECTURE.md`, `PRD.md`, `source/plugin/PluginProcessor.*` | **partagés** — sur `main`, en commit dédié |

`fixtures/` est **la spécification du comportement harmonique**. On ne modifie
jamais un cas pour faire passer un test, et une PR qui y touche ne se merge pas
sans revue d'Antoine.

---

## Méthode

- **TDD strict** : écrire le test, le lancer pour le voir **échouer**,
  implémenter, relancer.
- **Un test qui passe ne prouve rien tant qu'on n'a pas vérifié qu'il pouvait
  échouer.** Introduire le bug, capturer le rouge, restaurer, capturer le vert.
- Commits avec **pathspec explicite** : `git commit -m "msg" -- <fichiers>`,
  le `-m` avant le `--`. Pas de trailer `Co-Authored-By`.
- N'affirmer aucun résultat non exécuté. Un blocage rapporté vaut mieux qu'un
  succès prétendu.

## Agent skills

### Issue tracker

Les issues vivent dans les GitHub Issues de `c0remusic/tuple-vst`, pilotées via la CLI `gh`. Voir `docs/agents/issue-tracker.md`.

### Triage labels

Les cinq rôles canoniques, chaînes de label inchangées (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). Voir `docs/agents/triage-labels.md`.

### Domain docs

Single-context : `CONTEXT.md` + `docs/adr/` à la racine du dépôt. Voir `docs/agents/domain.md`.

### Wayfinder

Chantier trop gros pour une session : `/wayfinder` charte la carte sur le tracker ci-dessus. Labels `wayfinder:map` et `wayfinder:{research,prototype,grilling,task}` créés. Sous-issues et blocage natif GitHub disponibles — pas de repli par convention de corps.
