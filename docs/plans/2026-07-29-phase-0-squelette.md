# Phase 0 — Squelette jouable

> **Pour les workers agentiques :** SOUS-SKILL REQUISE — `superpowers:subagent-driven-development`
> ou `superpowers:executing-plans`. Les étapes utilisent la syntaxe checkbox (`- [ ]`).

**Révision 2** — corrigée après revue adverse du 2026-07-29 (11 findings, dont
3 critiques). Journal des corrections en fin de document.

**Objectif :** un plugin VST3 et CLAP qui se charge dans un DAW, expose ses six
paramètres, et joue un accord de la grille sans jamais laisser une note bloquée.

**Architecture :** trois couches, dépendances pointant vers l'intérieur.
`domain/` (règles harmoniques) ← `app/` (cas d'usage) ← `plugin/` (JUCE,
adaptateurs compris). **Rien sous `plugin/` n'inclut un en-tête JUCE** — c'est ce
qui garde la boucle de test à une seconde.

**Stack :** C++17, JUCE 9 (récupéré par CMake, version épinglée), CMake 4.4,
MSVC 14.44 (Windows) / Clang (macOS), `clap-juce-extensions` ou `clap-wrapper`.

---

## Global Constraints

Issues de `ARCHITECTURE.md`. Elles lient **toutes** les tâches.

### Licence — discipline, pas de garde automatique
- **Aucune dépendance copyleft, même transitive.**
- **Version de JUCE épinglée** dans le CMake. Jamais de branche flottante.
- **Jamais AAX ni ASIO.** `JUCE_USE_MP3AUDIOFORMAT` à 0, `JUCE_WEB_BROWSER` à 0.
- Toute dépendance ajoutée : licence vérifiée et notée dans la PR. Acceptables :
  MIT, Apache-2.0, ISC, BSD-2, BSD-3.

### Identifiants — définitifs à vie
```
Nom du fabricant   Tuple
Code fabricant     Tupl
Nom du plugin      Tuple
Code plugin        Chrd
Identifiant CLAP   live.tuple.chords
Bundle macOS       live.tuple.chords
```

### Thread audio
- **Zéro allocation, zéro lock, zéro I/O, zéro exception** dans `processBlock` et
  tout ce qu'il appelle. Buffers de taille fixe alloués dans `prepareToPlay`.
- **Toute note-on a son note-off garanti**, sur les **quatre** déclencheurs :
  changement d'accord, arrêt du transport, `releaseResources`, **destruction du
  plugin**.
- **Notes placées à leur offset d'échantillon exact**, jamais à 0.
- **Preuve : RealtimeSanitizer** (`-fsanitize=realtime`, Clang ≥ 20), chemins
  temps réel annotés `[[clang::nonblocking]]`. Sans lui, les trois points
  ci-dessus sont des intentions, pas des garanties.

### La règle la plus facile à casser par inadvertance
Les cas d'usage retournent des **structures de valeur de taille fixe**, sur la
pile. **Jamais de `std::vector`, `std::string`, `std::function` ni de `new` en
retour** — un objet alloué sur le thread audio glitche. L'appel virtuel coûte
quelques nanosecondes et ne pose aucun problème ; c'est l'allocation qui tue.

### Contraintes d'hôte
- Le plugin **expose un bus de sortie audio même inutilisé** : Live et Cakewalk
  refusent sinon de le charger.
- Il se charge **en position d'instrument**, pas en MIDI FX.

### Divers
- Windows **et** macOS dès le départ. Pas de Linux, pas d'AAX.
- ⚠️ **`register` est un mot réservé en C++.** L'identifiant de paramètre exposé
  au DAW est la chaîne `register` ; le champ C++ s'appelle **`centre`** partout.
  Ne pas « harmoniser » les deux.
- Commits avec pathspec explicite : `git commit -m "msg" -- <fichiers>`. Pas de
  trailer `Co-Authored-By`.
- CMake est installé hors `PATH` du shell : `export PATH="$PATH:/c/Program Files/CMake/bin"`.
  MSVC aussi : passer par `vcvars64.bat`.

---

### Task 1 : Dépendances et squelette de build

⚠️ **HITL — installations réseau, ne part pas en autonomie.**

**Files:** `CMakeLists.txt`, `.gitignore`, `source/plugin/PluginProcessor.{h,cpp}`,
`source/plugin/PluginEditor.{h,cpp}`

**Interfaces produites :** un `.vst3` et un `.clap` qui se chargent dans un DAW.

- [ ] **Step 1 — CMake récupère JUCE, on ne le clone pas à la main.**
  `FetchContent` avec un **tag épinglé**, pas une branche. Ça rend l'installation
  déclarative et identique sur le Mac de Stéphane.
- [ ] **Step 2 — `CMakeLists.txt`** avec `juce_add_plugin`, `FORMATS VST3`, les
  identifiants ci-dessus, et **explicitement sans** AAX ni ASIO. Définir
  `JUCE_USE_MP3AUDIOFORMAT=0` et `JUCE_WEB_BROWSER=0`.
- [ ] **Step 3 — Option de compilation RealtimeSanitizer.** Une option CMake
  `TUPLE_RTSAN` (OFF par défaut) qui ajoute `-fsanitize=realtime` sur les
  compilateurs qui le supportent. Task 7 s'en sert en CI.
- [ ] **Step 4 — Bus audio bidon.** Sans lui, Live refuse de charger :

```cpp
TupleProcessor::TupleProcessor()
    : AudioProcessor (BusesProperties()
        .withOutput ("Out", juce::AudioChannelSet::stereo(), true))
{}
bool TupleProcessor::acceptsMidi()  const override { return true;  }
bool TupleProcessor::producesMidi() const override { return true;  }
bool TupleProcessor::isMidiEffect() const override { return false; }
```

- [ ] **Step 5 — Compiler, charger dans un DAW, capturer la preuve** dans
  `proof/`. Le plugin apparaît et ne crashe pas.
- [ ] **Step 6 — Ajouter le CLAP** via `clap-juce-extensions` ou `clap-wrapper`.
  **Vérifier la licence du choix retenu et la noter dans le commit.**
- [ ] **Step 7 — Commit.**

---

### Task 2 : Le domaine harmonique

**Files:** `source/domain/{Key,Scale,Degree,ChordSpec,VoicingFamily,NoteEvent}.h`,
`ChordSpec.cpp`, `tests/domain_tests.cpp`

**Interfaces produites :**
```cpp
enum class VoicingFamily : uint8_t
    { Close, Open, Drop, Rootless, Quartal, TwoHand };

enum class Role : uint8_t
    { Root, Third, Fifth, Seventh, Ninth, Eleventh, Thirteenth, Sus };

struct ChordTone { uint8_t semitones; Role role; };

struct ChordSpec {
    uint8_t rootPc;                       // 0..11
    std::array<ChordTone, 6> tones;
    uint8_t count;                        // 1..6
    static std::optional<ChordSpec> make (uint8_t rootPc,
                                          std::initializer_list<ChordTone>);
};

struct NoteEvent { uint8_t pitch; uint8_t velocity; int sampleOffset; };

// L'état lisible du domaine — ARCHITECTURE.md §5 bis.
struct HarmonicContext { uint8_t key; uint8_t scaleIndex; ChordSpec current; };
```

⚠️ **Les rôles ne sont pas décoratifs.** `Rootless` doit retirer la
fondamentale, `Drop` doit descendre une voix précise : sans savoir quel
intervalle est la tierce ou la septième, ces deux familles ne sont pas
implémentables. C'est pourquoi `ChordSpec` porte des `ChordTone`, pas des
entiers nus.

`HarmonicContext` satisfait la contrainte de forme d'`ARCHITECTURE.md` §5 bis :
la gamme et l'accord courant sont un **état lisible**, pas un détail interne du
moteur. C'est ce qui permettrait un jour d'y brancher un guidage mélodique.

- [ ] **Step 1 — Écrire les tests d'abord, les lancer, les voir échouer.**
  Critères : `make` rejette `rootPc > 11` ; rejette 0 ou plus de 6 tons ;
  accepte un accord valide et conserve l'ordre des rôles.
- [ ] **Step 2 — Implémenter.**
- [ ] **Step 3 — Relancer, voir passer.**
- [ ] **Step 4 — Témoin de faillibilité.** Bug volontaire **précis** : dans
  `make`, remplacer la borne `rootPc > 11` par `rootPc > 12`. Lancer, capturer la
  sortie ROUGE. Restaurer. Relancer, capturer la sortie VERTE. Vérifier qu'aucune
  trace du bug ne subsiste.
- [ ] **Step 5 — Prouver l'étanchéité :** `grep -ri "juce" source/domain/` ne
  retourne **rien**. Rapporter la commande et sa sortie vide.
- [ ] **Step 6 — Commit.**

---

### Task 3 : La couture spec → notes et son corpus

**Files:** `source/domain/Voicing.{h,cpp}`, `fixtures/voicing_basic.txt`,
`tests/voicing_tests.cpp`

**Interfaces produites :**
```cpp
struct VoicingSettings { float openness; float density; uint8_t centre; };
struct RealizedChord { std::array<uint8_t, 8> notes; uint8_t count; };

RealizedChord realize (const ChordSpec&, VoicingFamily, const VoicingSettings&);
```
⚠️ `RealizedChord` est une **valeur de taille fixe** retournée par copie. Pas de
`std::vector`, pas d'allocation. `centre` est le champ C++ du paramètre exposé
sous le nom `register`.

- [ ] **Step 1 — Tests d'abord, les voir échouer.** Critères vérifiables :
  chaque note est à moins de 12 demi-tons de `centre` ; toute note est dans
  `0..127` ; deux appels identiques donnent le même résultat ; `Rootless` ne
  contient pas la classe de hauteur du rôle `Root` ; les six familles produisent
  au moins deux dispositions distinctes pour un même spec.
- [ ] **Step 2 — Implémenter.** En Phase 0, `realize` est **délibérément naïf** :
  chaque hauteur placée dans l'octave la plus proche de `centre`, la famille
  modifiant la répartition. Le vrai moteur le remplacera **derrière cette même
  signature**. Ne pas chercher à le rendre musical — le rendre correct et
  déterministe.
- [ ] **Step 3 — Relancer, voir passer.**
- [ ] **Step 4 — Témoin de faillibilité.** Bug volontaire **précis** : inverser
  la comparaison qui choisit l'octave la plus proche. ROUGE, restaurer, VERT,
  vérifier qu'il ne reste aucune trace.
- [ ] **Step 5 — Écrire `fixtures/voicing_basic.txt`.** Format **exact**, une
  ligne par cas, séparateur `|`, encodage UTF-8 sans BOM :

```
# SPÉCIFICATION. On ne modifie jamais un cas pour faire passer un test.
# rootPc | tones (semitones:role,...) | family | centre | notes attendues
0 | 0:Root,4:Third,7:Fifth | Close | 60 | 60,64,55
0 | 0:Root,4:Third,7:Fifth | Open | 60 | 60,64,67
```

  Au moins **18 cas** : six familles × trois accords (majeur, mineur,
  dominante 7). Ajouter un test qui lit le fichier et vérifie chaque ligne, et
  qui **échoue si le fichier est vide ou introuvable** — sinon il passe pour de
  mauvaises raisons.
- [ ] **Step 6 — Commit.**

---

### Task 4 : Les six paramètres

**Files:** `source/plugin/Params.h`, `source/plugin/ParameterAdapter.{h,cpp}`,
`source/plugin/PluginProcessor.{h,cpp}` (l'APVTS y vit), `tests/params_tests.cpp`

**Interfaces produites :**
```cpp
struct EngineSettings {              // aucun type JUCE
    uint8_t key; uint8_t scaleIndex; int8_t octave;
    float openness; float density; uint8_t centre;
};
EngineSettings readSettings (const juce::AudioProcessorValueTreeState&);
```

⚠️ **La liste des six est définitive** : la changer après diffusion casse les
projets sauvegardés. Identifiants exposés : `key`, `scale`, `octave`,
`openness`, `density`, `register`. **L'accord joué n'en fait pas partie.**

- [ ] **Step 1 — Déclarer le layout APVTS** dans `PluginProcessor`, avec
  exactement ces six paramètres, identifiants en chaînes stables, plages et
  valeurs par défaut explicites.
- [ ] **Step 2 — Écrire `ParameterAdapter`.** C'est **le seul endroit** où un
  type JUCE touche les réglages ; il produit un `EngineSettings` ordinaire.
- [ ] **Step 3 — Test :** l'adaptateur produit les bonnes valeurs aux deux bornes
  de chaque paramètre.
- [ ] **Step 4 — Test de persistance :** sauvegarder l'état, recharger, les six
  valeurs sont identiques. **Doit échouer si un paramètre est retiré du layout.**
- [ ] **Step 5 — Commit.**

---

### Task 5 : Jouer un accord, et le relâcher

**Files:** `source/app/{PlayChord,ReleaseAll}.{h,cpp}`,
`source/plugin/MidiEmitter.{h,cpp}`, `source/plugin/PluginProcessor.{h,cpp}`,
`tests/noteoff_tests.cpp`

**Interfaces produites :**
```cpp
struct ChordRequest { ChordSpec spec; VoicingFamily family;
                      VoicingSettings settings; int sampleOffset; };
struct NoteBatch { std::array<NoteEvent, 16> events; uint8_t count; };

NoteBatch playChord  (const ChordRequest&, const NoteBatch& sounding);
NoteBatch releaseAll (const NoteBatch& sounding, int sampleOffset);
```
`playChord` retourne **les note-offs du précédent ET les note-ons du nouveau**
dans le même lot. C'est ce qui rend l'invariant testable sans hôte.

- [ ] **Step 1 — Écrire le test de l'invariant, le voir échouer.** Rejouer une
  séquence et compter par hauteur : **toute note-on a exactement une note-off.**
  Couvrir les **quatre** déclencheurs, un cas de test chacun : changement
  d'accord, arrêt du transport, `releaseResources`, **destruction du plugin**.
- [ ] **Step 2 — Implémenter les deux cas d'usage.** Aucune allocation, aucun
  type JUCE, aucun `unwrap` implicite.
- [ ] **Step 3 — Relancer, voir passer.**
- [ ] **Step 4 — Témoin de faillibilité.** Bug volontaire **précis** : retirer la
  génération des note-offs dans `playChord`. ROUGE sur les quatre cas, restaurer,
  VERT, vérifier qu'il ne reste aucune trace.
- [ ] **Step 5 — Écrire `MidiEmitter`** : `NoteBatch` → `juce::MidiBuffer`, **à
  l'offset d'échantillon porté par chaque événement**. Test dédié : un événement
  à l'offset 128 arrive bien à 128 dans le buffer, pas à 0.
- [ ] **Step 6 — Câbler dans `processBlock`** avec un buffer d'état de taille
  fixe. Appeler `releaseAll` depuis `releaseResources`, à la perte du transport,
  **et depuis le destructeur `~TupleProcessor()`**.
- [ ] **Step 7 — Commit.**

---

### Task 6 : La grille

**Files:** `source/app/BuildGrid.{h,cpp}`, `tests/grid_tests.cpp`

**Interfaces produites :**
```cpp
inline constexpr uint8_t kDegrees        = 7;
inline constexpr uint8_t kChordTypes     = 12;   // cf. PRD, types de la grille
inline constexpr uint8_t kBorrowedSlots  = 12;
inline constexpr uint16_t kMaxGridCells  = kDegrees * kChordTypes + kBorrowedSlots;

struct GridCell { ChordSpec spec; uint8_t degree; bool borrowed; };
struct Grid { std::array<GridCell, kMaxGridCells> cells; uint16_t count; };

Grid buildGrid (uint8_t key, uint8_t scaleIndex);
```
La taille est **dérivée de constantes nommées**, pas un nombre magique.

- [ ] **Step 1 — Tests d'abord, les voir échouer.** Critères : les sept degrés
  diatoniques sont présents ; les accords empruntés sont présents et marqués
  `borrowed` ; aucune cellule ne porte un `ChordSpec` invalide ; `count` ne
  dépasse jamais `kMaxGridCells`.
- [ ] **Step 2 — Implémenter.** Aucune allocation.
- [ ] **Step 3 — Relancer, voir passer.**
- [ ] **Step 4 — Commit.**

---

### Task 7 : Validation automatisée

**Files:** `.github/workflows/ci.yml`

- [ ] **Step 1 — Matrice deux OS**, Windows et macOS, dès le premier workflow.
- [ ] **Step 2 — Compiler et lancer le binaire de test** (`domain` + `app`, sans
  JUCE, donc rapide). Bloquant.
- [ ] **Step 3 — Compilation RealtimeSanitizer** (`-DTUPLE_RTSAN=ON`, Clang ≥ 20)
  et exécution du chemin audio sous le sanitizer. **C'est la preuve des
  invariants du thread audio** — allocations, syscalls, verrous, exceptions.
  Bloquant. Si RTSan n'est pas disponible sur un runner, le dire explicitement
  dans les logs plutôt que de passer silencieusement.
- [ ] **Step 4 — `clap-validator validate`** sur le `.clap`. Seul validateur dont
  la couverture note on/off et événements MIDI est documentée. Archiver la sortie
  dans `proof/`.
- [ ] **Step 5 — `pluginval --strictness-level 5`** sur le `.vst3`. Exit code 0
  ou 1, contractualisé.
- [ ] **Step 6 — Prouver que la CI peut échouer.** Pousser une branche jetable
  avec les note-offs retirés, vérifier qu'elle est **rejetée**, capturer la
  sortie, supprimer la branche.
- [ ] **Step 7 — Commit.**

---

## Hors périmètre de cette phase

| exclu | raison |
|---|---|
| **`VoiceLeading.h/.cpp`** | Le mouvement entre accords fait partie du moteur de voicing, non spécifié. Le fichier est prévu dans `ARCHITECTURE.md` §5 mais **n'est pas créé en Phase 0**. |
| Le vrai moteur de voicing | Non spécifié. Le placeholder de Task 3 occupe la couture. |
| L'UI définitive | Reconstruite de zéro, beaucoup de fonctions vont changer. Task 1 ne pose qu'un éditeur vide. |
| Le mapping note MIDI vers cellule | Convention publique, à figer avant diffusion, pas avant le squelette. |
| Le tiroir Progression, l'expression | Décidés au périmètre, non spécifiés. |
| Tupline | Hors périmètre v1. `HarmonicContext` garde la porte ouverte. |
| macOS AU, Logic | Après la v1. |
| Compte Apple Developer, notarisation | Nécessaires pour **livrer** sur Mac, pas pour développer. |

---

## Journal des corrections — révision 2

Revue adverse du 2026-07-29. Onze findings, tous traités.

| # | finding | traitement |
|---|---|---|
| C1 | `Register` portait trois noms et deux types (`registre`, `centre`, `Register`) | Unifié : identifiant exposé `register`, champ C++ `centre` partout. Cause documentée — `register` est un mot réservé en C++. |
| C2 | Quatre couches dans le plan contre structure plate dans `ARCHITECTURE.md`, jamais arbitré | **Tranché : trois couches.** `ARCHITECTURE.md` §5 réécrit pour dire la même chose. |
| C3 | RealtimeSanitizer absent de toutes les tâches alors que §6 en fait la preuve | Ajouté en Task 1 Step 3 (option CMake) et Task 7 Step 3 (CI bloquante). |
| I1 | `VoiceLeading.h/.cpp` disparaissait sans être déclaré hors périmètre | Déclaré explicitement hors périmètre Phase 0. |
| I2 | `ChordSpec` sans rôles harmoniques, alors que `Rootless` et `Drop` en ont besoin | `ChordTone { semitones, role }` introduit, avec la justification. |
| I3 | La contrainte « le domaine expose la gamme et l'accord courant » n'était couverte nulle part | `HarmonicContext` ajouté en Task 2. |
| I4 | `releaseAll` ne couvrait que 2 des 4 déclencheurs | Les quatre sont nommés, un cas de test chacun, destructeur inclus. |
| I5 | Task 4 ne listait pas `PluginProcessor` alors que l'APVTS y vit | Ajouté aux fichiers de la tâche. |
| m1 | Format du fichier de fixtures laissé à l'improvisation | Format exact spécifié, avec exemple et échec si fichier vide. |
| m2 | Constante `96` de la grille sortie de nulle part | Dérivée de constantes nommées. |
| m3 | « Introduire un bug volontaire » sans dire lequel | Le bug précis est nommé dans chacune des trois tâches concernées. |
