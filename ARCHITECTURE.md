# ARCHITECTURE — Tuple VST

**Date : 2026-07-29.** Chaque choix est adossé à une vérification datée. Ce qui
n'a pas été vérifié est marqué comme tel.

Ce document décrit **le COMMENT**. Le QUOI vit dans `PRD.md`.

> **Le VST repart de zéro.** Le device Max for Live sert de **référence
> fonctionnelle** — on s'en inspire pour décider quoi construire. Aucun code
> n'en est repris par défaut ; toute reprise éventuelle serait une décision
> explicite.

---

## 1. Vue d'ensemble

**Un seul langage, une seule chaîne de build : C++17 / JUCE 9.**

```
                  ┌───────────────────────────┐
                  │  harmony/  (C++ pur)      │
                  │  aucune dépendance JUCE   │
                  │  spec → notes             │
                  └────────────┬──────────────┘
                               │  appel direct (pas de frontière)
              ┌────────────────┼────────────────┐
              │                                 │
    ┌─────────▼──────────┐            ┌─────────▼──────────┐
    │ PluginProcessor    │            │ tests/             │
    │ thread audio       │            │ corpus de fixtures │
    │ VST3 · CLAP        │            │ boucle rapide      │
    └────────────────────┘            └────────────────────┘
              │
    ┌─────────▼──────────┐
    │ PluginEditor       │
    │ UI native JUCE     │
    └────────────────────┘
```

**La couture** reste `spec → notes` : une spécification d'accord (hauteurs et
rôles harmoniques, sans octaves) entre, des notes MIDI sortent. Elle est ici une
**frontière de classe C++**, pas une frontière de langage.

**`harmony/` ne dépend pas de JUCE.** C'est ce qui le rend testable par un
binaire de test qui démarre en une seconde, sans hôte audio. C'est la seule
boucle rapide du projet.

### Les deux boucles, et leur vitesse réelle

| boucle | ce qu'elle valide | coût |
|---|---|---|
| `harmony/` + corpus de fixtures | la **correction** : les bonnes notes, de façon déterministe | compilation d'un binaire de test, quelques secondes |
| plugin chargé dans un DAW | le **goût** : est-ce que ça sonne, est-ce que ça se joue | compiler, bundler, recharger l'hôte, rejouer |

⚠️ **Il n'y a pas de boucle rapide pour l'oreille.** Les deux options envisagées
— module WebAssembly auditionné au navigateur, et cible standalone JUCE — ont
été écartées. Concevoir un système de voicing est une activité d'oreille : cette
lenteur est un coût assumé, pas un oubli.

---

## 2. La stack

| couche | technologie | licence | note |
|---|---|---|---|
| Tout le code | **C++17**, **JUCE 9** | JUCE (voir §3) | Un langage, un écosystème, une chaîne de build. |
| Formats | **VST3** + **CLAP** | — | ⚠️ **JUCE ne produit pas de CLAP nativement** : il faut `clap-juce-extensions` ou `clap-wrapper`, tous deux MIT. |
| Build | **CMake** | — | Voie recommandée par JUCE. |
| Compilateurs | **MSVC 14.44** (Windows) · **Clang/Xcode** (macOS) | — | MSVC et MSBuild déjà installés côté Windows. |
| Paramètres et état | `AudioProcessorValueTreeState` | JUCE | Le pont thread-safe imposé par JUCE entre l'UI et le thread audio. Accès atomique, automation, presets, sans lock sur le thread audio. |
| UI | Composants natifs JUCE | JUCE | L'UI est reconstruite de zéro (voir `PRD.md`). |
| Preuve temps réel | **RealtimeSanitizer** (`-fsanitize=realtime`, Clang ≥ 20) | — | Couvre allocations, syscalls, locks et exceptions. Disponible sur les deux plateformes. |
| Validation | **clap-validator**, **pluginval** | MIT | Le premier est le seul validateur dont la couverture note on/off et événements MIDI est documentée. |

### Pourquoi pas un cœur en Rust

Option envisagée puis écartée le 2026-07-29. Ce qui la portait était la
compilation du cœur en WebAssembly pour auditionner le voicing au navigateur ;
cette boucle n'est pas jugée utile. Ce qui restait — sûreté mémoire sur le cœur —
ne compensait pas deux langages, deux chaînes de build et une frontière FFI
**non vérifiée sur macOS**, dans un binôme dont un développeur débute.

Mesures conservées pour mémoire, elles n'ont pas départagé : la frontière C ABI
coûtait **+0,64 ns/appel** en lien statique contre un budget de callback de
**2,67 ms** à 48 kHz en buffer 128. La latence ne dépendait pas du langage.

⚠️ **Coût réel de cet abandon** : on perd `cargo deny check licenses`, un garde-fou
**mécanique** qui bloquait toute dépendance copyleft, y compris transitive, et
dont la capacité à refuser avait été prouvée. En C++, la protection du §4 redevient
de la **discipline vérifiable à la revue**, pas une commande qui échoue.

---

## 3. Licence JUCE — coût et pièges

Vérifié le 2026-07-29 sur l'EULA, pas sur la page marketing.

| tier | plafond de revenu / financement | par développeur | à deux |
|---|---|---|---|
| **Starter** | ≤ **20 000 $** / 12 mois | **gratuit** | **0 $** |
| Indie | ≤ 300 000 $ | 40 $/mois **ou** 800 $ perpétuel | 80 $/mois ou 1 600 $ |
| Pro | illimité | 175 $/mois (**engagement 12 mois**) ou 3 500 $ perpétuel | 4 200 $/an |

- **Source fermée autorisée à tous les tiers**, Starter compris.
- **Aucun splash screen.** Le mécanisme a été supprimé du code en JUCE 8 : le
  fichier `juce_JUCESplashScreen.h` renvoie 404 au tag `8.0.9` et un
  avertissement de compilation signale que le flag est ignoré. Aucune clause
  d'attribution visuelle dans l'EULA.
- **Une licence par développeur** touchant au code. Deux personnes = deux sièges.
  Les machines de build et de test n'en consomment pas.
- ⚠️ **Le plafond porte sur le revenu de l'entité entière.** Pour une personne
  physique, c'est le revenu tiré de l'usage du framework. Pour une société,
  « *the total revenue or funding received by the entity and all its Affiliates …
  from all sources, whether it be received in connection with the entity's use of
  the Framework or not, without offsets of any kind* ». **La forme juridique
  choisie pour se répartir les revenus change le tier à payer.**
- ⚠️ **Sur abonnement, cesser de payer oblige à cesser de distribuer**, sauf
  rachat en perpétuel.
- Une licence perpétuelle ne couvre **qu'une version majeure**.
- L'alternative copyleft est **AGPLv3** depuis JUCE 8. On ne la choisit pas.

**Pourquoi JUCE 9 et pas 8** : le SDK VST3 embarqué dans **8.0.9** est encore en
double licence propriétaire/GPLv3 et sa voie propriétaire exige « *a copy of the
License Agreement signed by Steinberg* ». Celui de **JUCE 9** est **MIT**. Même
prix, même EULA, une formalité en moins.

⚠️ **Les modules ISC ont disparu.** En JUCE 7, `juce_core`, `juce_events`,
`juce_audio_basics` et `juce_audio_devices` étaient sous ISC. Cette phrase est
absente de `LICENSE.md` en 8 et 9 : **toute la bibliothèque est sous le même
régime**.

---

## 4. Politique de licence

**Aucune dépendance copyleft, même transitive.** Le produit est fermé et
commercial.

Il n'existe plus de garde-fou automatique (§2). La protection tient en quatre
règles, à vérifier en revue :

| règle | raison |
|---|---|
| **Épingler la version de JUCE** dans le CMake, jamais de branche flottante | une version majeure change le régime de licence du SDK VST3 embarqué |
| **Ne jamais activer la cible AAX** | SDK Avid, propriétaire **ou GPLv3** |
| **Ne jamais activer la cible ASIO** | SDK Steinberg, propriétaire **ou GPLv3** |
| **Laisser `JUCE_USE_MP3AUDIOFORMAT` à 0** | JUCE avertit lui-même : « *NOT guaranteed to be free from infringements of 3rd-party intellectual property* » |

Toute dépendance ajoutée au CMake fait l'objet d'une vérification de licence
explicite, notée dans la PR. Licences acceptables : `MIT`, `Apache-2.0`, `ISC`,
`BSD-2-Clause`, `BSD-3-Clause`, plus la licence commerciale JUCE.

Les autres dépendances embarquées par JUCE sont permissives (FLAC et Ogg Vorbis
en BSD, HarfBuzz, zlib, CHOC en ISC…). **Aucune dépendance LGPL ni GPL-seule.**
`JUCE_WEB_BROWSER` reste à 0 : inutile ici, et c'est ce qui charge WebKitGTK.

---

## 5. Structure du projet

**Trois couches**, dépendances pointant vers l'intérieur. Tranché le 2026-07-29.

```
tuple-vst/
├── CMakeLists.txt          racine — PARTAGÉ
├── PRD.md · ARCHITECTURE.md   PARTAGÉS
├── source/
│   ├── domain/             ANTOINE — règles harmoniques, AUCUN JUCE
│   │   ├── Key.h  Scale.h  Degree.h
│   │   ├── ChordSpec.h/.cpp    hauteurs + RÔLES, sans octaves
│   │   ├── VoicingFamily.h     les six familles
│   │   ├── Voicing.h/.cpp      la couture : spec → notes
│   │   ├── VoiceLeading.h/.cpp mouvement entre accords
│   │   └── NoteEvent.h
│   ├── app/                ANTOINE — cas d'usage, AUCUN JUCE
│   │   ├── BuildGrid.h/.cpp
│   │   ├── PlayChord.h/.cpp
│   │   └── ReleaseAll.h/.cpp
│   └── plugin/             JUCE, adaptateurs compris
│       ├── PluginProcessor.h/.cpp  thread audio, note-off garanti
│       ├── PluginEditor.h/.cpp     UI — STÉPHANE
│       ├── Params.h                layout APVTS
│       ├── MidiEmitter.h/.cpp      NoteBatch → juce::MidiBuffer
│       └── ParameterAdapter.h/.cpp APVTS → EngineSettings
├── fixtures/               ANTOINE SEUL — la spécification exécutable
├── tests/                  binaire de test, sans JUCE, boucle rapide
├── hosts/                  STÉPHANE — matrice DAW et guides de routage
├── proof/                  témoins datés et signés
└── .github/workflows/      CI matrice Windows + macOS
```

**La règle qui tient tout : rien sous `plugin/` n'inclut un en-tête JUCE.**
`domain/` et `app/` compilent seuls, et le binaire de test les compile tous les
deux — il démarre en une seconde, sans hôte audio. Si un fichier de `domain/` ou
`app/` a besoin d'inclure JUCE, c'est que la frontière a été franchie au mauvais
endroit.

**Pourquoi trois et pas quatre.** Une quatrième couche d'adaptateurs isolée
n'achèterait rien ici : elle ne contiendrait que la traduction MIDI et la lecture
des paramètres, deux briques intrinsèquement liées à JUCE dont **aucune n'aura
jamais de seconde implémentation**. La règle de dépendance sert à pouvoir
échanger une implémentation ; sans second candidat, le niveau supplémentaire est
de la cérémonie. Les adaptateurs vivent donc dans `plugin/`.

**Pourquoi pas une structure plate.** L'orchestration — relâcher l'accord
précédent, émettre le nouveau au bon offset — finirait dans `processBlock`.
C'est exactement l'endroit où se cache le bug de note-off, et il deviendrait
intestable sans hôte. Or « aucune note bloquée » est une promesse produit.

---

## 5 bis. Paramètres, état et identifiants

Tranché le 2026-07-29. **Ces trois listes sont définitives au sens où les changer
après la première vente casse les projets sauvegardés des utilisateurs.**

### Les six paramètres automatisables

Un paramètre obtient une piste d'automation dans le DAW, se sauvegarde et se
module. Il n'y en a que six :

| paramètre | type | note |
|---|---|---|
| Key | 12 valeurs | la tonique |
| Scale | énumération | la gamme |
| Octave | entier borné | le registre de base |
| Openness | flottant | ouverture — contraint le moteur |
| Density | flottant | densité — contraint le moteur |
| Register | flottant | centre de placement — contraint le moteur |

⚠️ **`register` est un mot réservé en C++.** L'identifiant de paramètre exposé au
DAW est bien la chaîne `register`, mais le champ C++ correspondant s'appelle
`centre` partout dans le code. Ne pas « corriger » cette différence : elle est
délibérée, et renommer l'identifiant exposé casserait les projets sauvegardés.

**L'accord joué n'est PAS un paramètre.** Il ne s'automatise pas depuis la
timeline. Conséquence voulue : la grille reste un instrument, et sa taille n'est
pas figée par des automations existantes.

### L'état sérialisé, non automatisable

- La progression capturée
- Les forçages par accord (famille de voicing, inversion, variation)
- L'état d'ouverture du tiroir Progression

### Le déclenchement

Deux entrées, pas d'automation : **la souris** sur une cellule, et **une note
MIDI entrante**. Le second permet d'enregistrer ses déclencheurs en MIDI dans le
DAW et de les rejouer à l'identique.

⚠️ **Le mapping note vers cellule devient une convention publique.** Le changer
après diffusion casserait les enregistrements MIDI des utilisateurs. À figer
avant la première version publique — non figé au 2026-07-29.

### Les familles de voicing

**Il n'y a pas de catalogue de 28 types.** Le moteur décide ; l'utilisateur peut
forcer une **famille** sur un accord précis. Six familles, chacune une manière
structurellement distincte de répartir les mêmes notes :

`Close` · `Open` · `Drop` · `Rootless` · `Quartal` · `Two-hand`

Les noms évoquant un genre musical (`house`, `trance`, `funk`, `frenchtouch`,
`deeptech`…) du device Max for Live **disparaissent** : ce n'étaient pas des
familles mais des préréglages, et « genre » n'est pas un concept produit.

### Les identifiants — définitifs à vie

| champ | valeur |
|---|---|
| Nom du fabricant | `Tuple` |
| Code fabricant | `Tupl` |
| Nom du plugin | `Tuple` |
| Code plugin | `Chrd` |
| Identifiant CLAP | `live.tuple.chords` |
| Identifiant de bundle macOS | `live.tuple.chords` |

Le code plugin `Chrd` laisse la place à un futur `Mldy` — même fabricant, produit
différent, aucun conflit.

### Une contrainte de forme sur la couche domaine

`source/domain/` **expose la gamme courante et la spécification de l'accord
courant comme un état lisible**, pas comme un détail interne du moteur de
voicing. Ça ne coûte rien aujourd'hui, c'est la bonne forme de toute façon, et
c'est ce qui permettrait un jour d'y brancher un guidage mélodique sans toucher
au moteur d'accords.

---

## 6. Invariants du thread audio

Non négociables. Le point 3 est une promesse produit.

1. **Zéro allocation, zéro lock, zéro I/O** dans `processBlock` et tout ce qu'il
   appelle. Buffers de taille fixe, alloués dans `prepareToPlay`.
2. **Zéro exception** sur le chemin audio.
3. **Toute note-on a son note-off garanti** — changement d'accord, arrêt du
   transport, `releaseResources`, déchargement du plugin. Testé, pas supposé.
   C'est le bug ouvert depuis 2020 chez le concurrent.
4. **Les notes sont placées à leur offset d'échantillon exact** —
   `midiMessages.addEvent(msg, sampleOffset)`, jamais à 0. C'est ce que
   `MidiBuffer` permet et ce que VST3 (`Event::sampleOffset`) et CLAP
   (`header.time`) transportent.

**Preuve** : RealtimeSanitizer (`-fsanitize=realtime`, Clang ≥ 20) sur une
compilation dédiée, en CI. Les contextes temps réel sont marqués
`[[clang::nonblocking]]`.

---

## 7. Plateformes

**Windows et macOS dès le premier jour** — Antoine développe sous Windows,
Stéphane sous macOS. Ce n'est pas un port différé.

- **Formats v1** : VST3 + CLAP. **AU** devient atteignable grâce au poste macOS
  (AUv2 est macOS-only, SDK Apple sous Apache 2.0) — à décider.
- **Pas d'AAX** : compte Avid, clé iLok, adhésion supposant un produit déjà en vente.
- **Pas de Linux** : supprime la question LGPL de WebKitGTK.
- ⚠️ **macOS impose un compte Apple Developer (99 $/an) et la notarisation.**
  Un plugin non notarisé est bloqué par Gatekeeper chez le client. C'est sur le
  chemin critique, pas une finition.
- ⚠️ **Apple Silicon ou Intel** — non établi. Détermine si on livre un binaire
  universel ou seulement `arm64`.
- **CI en matrice deux OS** dès le départ.

### Contraintes imposées par les hôtes

- Le plugin **expose un bus de sortie audio même inutilisé** : Live et Cakewalk
  refusent de charger un plugin MIDI-only. Le contournement est en dur dans
  l'exemple officiel de JUCE.
- Il se charge **en position d'instrument**, pas en MIDI FX : Live n'a pas de
  slot MIDI-effect pour VST/AU.
- **Live n'achemine ni les CC ni le pitch bend émis en VST3.** Non réparable de
  notre côté.
- **Live fusionne tous les canaux MIDI** en routage inter-pistes.

---

## 8. Propriété de fichiers

Aucun mécanisme de verrouillage entre agents n'existe : la seule protection est
la disjonction déclarée à l'avance.

| zone | propriétaire |
|---|---|
| `source/domain/`, `source/app/`, `fixtures/`, `tests/` | Antoine — `fixtures/` est la spécification du produit |
| `source/plugin/PluginEditor.*`, `hosts/`, CI | Stéphane |
| `CMakeLists.txt`, `ARCHITECTURE.md`, `PRD.md`, `source/plugin/PluginProcessor.*` | **partagés** — modifiés sur `main`, en commit dédié |

Une PR touchant `fixtures/` ne se merge jamais sans revue d'Antoine.

---

## 9. Non décidé

1. **Le mapping note MIDI vers cellule** (§5 bis) — convention publique, à figer
   avant la première version publique.
2. **Le moteur d'expression** — un moteur servant le jeu et l'export, ou deux
   chemins. Couture d'architecture : à trancher avant d'écrire le moteur.
3. **`clap-juce-extensions` ou `clap-wrapper`** pour le CLAP. Les deux sont MIT.
4. **AU / Logic** dans la v1 ou après.
5. **Apple Silicon seul ou binaire universel** — dépend du Mac de Stéphane.
6. **Le compte Apple Developer** (99 $/an) et la notarisation — obligatoires pour
   livrer sur macOS, sur le chemin critique.
7. **Le prix.** Zone déduite du marché : 59 à 79 $.
8. **La forme juridique** de la collaboration — elle détermine le tier JUCE (§3).
9. **La répartition entre les deux développeurs** — non décidée au 2026-07-29.
   Personne n'a renoncé à quoi que ce soit ; à trancher avant la première vente.

### Tranché le 2026-07-29 — ne pas rediscuter sans décision datée qui remplace

- Tout en C++/JUCE, pas de cœur en Rust.
- Six paramètres automatisables, l'accord joué n'en est pas un.
- Six familles de voicing, pas de catalogue de 28 types.
- Les identifiants de plugin (§5 bis).
- Déclenchement souris et note MIDI entrante, pas d'automation de grille.
- Tupline hors périmètre v1 ; la couche domaine garde la porte ouverte.
