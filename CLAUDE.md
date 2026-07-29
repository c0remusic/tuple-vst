# CLAUDE.md — Tuple VST

Plugin d'accords **MIDI-only** pour DAW. Il produit des notes MIDI et rien
d'autre : aucun son, aucun traitement audio. L'argument du produit est la
**qualité du voicing et du mouvement entre accords**.

Les documents de référence sont `PRD.md` (le QUOI) et `ARCHITECTURE.md` (le
COMMENT). Ce fichier n'est qu'un condensé opérationnel : **en cas de
contradiction, les deux documents font foi.** Avant toute décision de fond,
lire la section correspondante plutôt que de se fier au résumé ci-dessous.

Langue : la documentation et les messages de commit sont en **français**. Le
code et les identifiants sont en anglais.

---

## Stack

C++17 · JUCE 9 · CMake. Formats v1 : **VST3 + CLAP**. Plateformes v1 :
**Windows et macOS** dès le départ, CI en matrice deux OS.

Pas de Rust, pas de WebAssembly — option envisagée et écartée le 2026-07-29
(`ARCHITECTURE.md` § 2).

---

## Règles non négociables

### 1. `source/harmony/` ne compile pas contre JUCE

C'est du C++ pur, sans aucune dépendance JUCE. C'est ce qui garde la boucle de
test rapide : un binaire qui démarre en une seconde, sans hôte audio.

**Si un fichier de `harmony/` a besoin d'un en-tête JUCE, c'est que la
frontière a été franchie au mauvais endroit.** Ne pas ajouter l'include —
remonter le problème.

La couture est `spec → notes` : une spécification d'accord (hauteurs et rôles
harmoniques, **sans octaves**) entre, des notes MIDI sortent.

### 2. Invariants du thread audio

Dans `processBlock` et tout ce qu'il appelle :

- **Zéro allocation, zéro lock, zéro I/O.** Buffers de taille fixe, alloués
  dans `prepareToPlay`.
- **Zéro exception** sur le chemin audio.
- **Toute note-on a son note-off garanti** — changement d'accord, arrêt du
  transport, `releaseResources`, déchargement du plugin. C'est une promesse
  produit, testée et non supposée : c'est le bug ouvert depuis 2020 chez le
  concurrent.
- **Offset d'échantillon exact** : `midiMessages.addEvent(msg, sampleOffset)`,
  jamais à 0.

Les contextes temps réel sont marqués `[[clang::nonblocking]]` et prouvés par
RealtimeSanitizer en CI.

### 3. `fixtures/` est la spécification

Le corpus de cas **est** la spécification du comportement harmonique.

**On ne modifie jamais un cas pour faire passer un test.** Si un test échoue,
c'est le code qui est faux — ou alors le cas doit être rediscuté explicitement,
jamais réécrit en silence. Une PR touchant `fixtures/` ne se merge pas sans
revue d'Antoine.

### 4. Aucune dépendance copyleft, même transitive

Le produit est fermé et commercial. Il n'existe **aucun garde-fou
automatique** : la protection est de la discipline à la revue.

Licences acceptables : `MIT`, `Apache-2.0`, `ISC`, `BSD-2-Clause`,
`BSD-3-Clause`, plus la licence commerciale JUCE. Toute dépendance ajoutée au
CMake fait l'objet d'une vérification de licence explicite, **notée dans la
PR**.

Quatre interdits durs :

| règle | raison |
|---|---|
| Épingler la version de JUCE, jamais de branche flottante | une version majeure change le régime de licence du SDK VST3 embarqué |
| Ne jamais activer la cible **AAX** | SDK Avid, propriétaire ou GPLv3 |
| Ne jamais activer la cible **ASIO** | SDK Steinberg, propriétaire ou GPLv3 |
| `JUCE_USE_MP3AUDIOFORMAT` reste à `0` | JUCE avertit lui-même sur la PI tierce |

`JUCE_WEB_BROWSER` reste à `0` (c'est ce qui charge WebKitGTK).

### 5. Le déterminisme

Mêmes entrées, mêmes notes. C'est ce qui rend le corpus de cas possible. Aucune
source d'aléa non graine dans le moteur.

---

## Le modèle harmonique : deux axes, et seulement deux

C'est la décision structurante du produit. Ne pas en introduire un troisième.

- **Axe 1 — QUEL accord** : ce qui change les hauteurs. Variation (même degré,
  autre qualité), extension (cas particulier de variation), substitution (autre
  fondamentale, même fonction).
- **Axe 2 — COMMENT il est disposé** : ce qui change la répartition des mêmes
  hauteurs sur le registre. Type de voicing, inversion.

Règle arrêtée : **la notation slash est la vérité de la basse** (`C/E` = mi à
la basse).

Le concurrent en expose cinq qui se recouvrent, et c'est le reproche
principal qu'on lui fait. Détail en `PRD.md` § 4.

---

## Principes produit

1. **La grille est la fonctionnalité principale** — maximum d'accords valides
   affichés pour la tonalité et la gamme.
2. **Aucun accord caché** derrière une page, un menu ou un assistant. Les
   accords empruntés restent dans la grille principale.
3. **Le mode avancé révèle des réglages, jamais il ne cache des accords.**
4. **La basse est jouée par un instrument séparé** — le plugin sort l'accord
   seul, tenant sur une main. Seul le mode `piano` fait exception.
5. **Ce qui est exporté doit être ce qui a été entendu** — l'export MIDI n'est
   pas un second chemin de code.

---

## Hors périmètre v1

Ne pas proposer, ne pas implémenter : banque de sons interne, hosting de
plugins, détection d'accords depuis l'audio, générateur de mélodie / arpèges /
patterns, Linux, AAX / Pro Tools. Chaque exclusion est adossée à un reproche
documenté fait au concurrent (`PRD.md` § 9).

---

## Structure

```
tuple-vst/
├── CMakeLists.txt          racine — PARTAGÉ
├── PRD.md · ARCHITECTURE.md   PARTAGÉS
├── source/
│   ├── harmony/            C++ pur, AUCUNE dépendance JUCE
│   │   ├── ChordSpec.h/.cpp    hauteurs + rôles, sans octaves
│   │   ├── Voicing.h/.cpp      la couture : spec → notes
│   │   └── VoiceLeading.h/.cpp mouvement entre accords
│   ├── PluginProcessor.h/.cpp  thread audio, note-off garanti
│   ├── PluginEditor.h/.cpp     UI
│   └── Params.h                layout APVTS
├── fixtures/               la spécification exécutable
├── tests/                  binaire de test, sans JUCE, boucle rapide
├── hosts/                  matrice DAW et guides de routage
├── proof/                  témoins datés et signés
└── .github/workflows/      CI matrice Windows + macOS
```

### Propriété de fichiers

Aucun verrou technique n'existe — la seule protection est la disjonction
déclarée. **Ne pas modifier une zone dont on n'est pas propriétaire sans le
dire explicitement.**

| zone | propriétaire |
|---|---|
| `source/harmony/`, `fixtures/`, `tests/` | Antoine |
| `source/PluginEditor.*`, `hosts/`, CI | Stéphane |
| `CMakeLists.txt`, `PRD.md`, `ARCHITECTURE.md`, `source/PluginProcessor.*` | partagés — sur `main`, en commit dédié |

---

## Questions ouvertes — ne pas trancher seul

Ces points sont **délibérément non décidés**. Les rencontrer n'est pas un
oubli : demander, ne pas choisir par défaut.

1. **Le moteur d'expression** (humanize, strum, vélocité) — un moteur servant
   le jeu temps réel *et* l'export, ou deux chemins ? Couture d'architecture, à
   trancher **avant** d'écrire le moteur.
2. **`clap-juce-extensions` ou `clap-wrapper`** pour le CLAP (les deux sont MIT).
3. **Sortie vers un port MIDI virtuel** — dans le périmètre v1 ou pas.
4. **AU / Logic** dans la v1 ou après.
5. **Apple Silicon seul ou binaire universel.**
6. **Prix**, **forme juridique**, **répartition entre les deux développeurs** —
   décisions humaines, hors du champ d'un agent.

---

## Contraintes imposées par les hôtes

À connaître avant de « corriger » ce qui ressemble à un bug :

- Le plugin **expose un bus de sortie audio même inutilisé** — Live et Cakewalk
  refusent sinon de charger un plugin MIDI-only. Ce n'est pas un oubli.
- Il se charge **en position d'instrument**, pas en MIDI FX.
- **Live n'achemine ni les CC ni le pitch bend émis en VST3.** Non réparable de
  notre côté — à documenter, pas à contourner.
- **Live fusionne tous les canaux MIDI** en routage inter-pistes.

---

## Travail et git

- Développer sur une branche, jamais directement sur `main`.
- Les PR touchant `fixtures/` exigent une revue d'Antoine.
- Toute dépendance ajoutée : licence vérifiée et notée dans la PR.
- Il n'y a **pas de boucle rapide pour l'oreille** : `harmony/` + corpus
  valident la *correction*, pas le *goût*. Ne pas affirmer qu'un voicing
  « sonne bien » — ça se juge dans un DAW, par un humain.
