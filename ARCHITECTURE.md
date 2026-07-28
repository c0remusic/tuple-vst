# ARCHITECTURE — Tuple VST

**Date : 2026-07-29.** Chaque choix ci-dessous est adossé à une vérification
datée. Ce qui n'a pas été vérifié est marqué comme tel.

Ce document décrit **le COMMENT**. Le QUOI vit dans `PRD.md`.

---

## 1. Vue d'ensemble

Un cœur de logique musicale en **Rust**, pur et sans dépendance, exposé par une
frontière **C ABI**, consommé par trois frontends :

```
                      ┌──────────────────────────┐
                      │  crates/harmony (Rust)   │
                      │  no_std · zéro dépendance│
                      │  spec → notes            │
                      └────────────┬─────────────┘
                                   │  C ABI (40 lignes)
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
    │ plugin/ (JUCE)   │  │ audition (WASM) │  │ mid-export (CLI)│
    │ VST3 · CLAP      │  │ navigateur      │  │ .mid            │
    │ le produit       │  │ boucle d'écoute │  │ témoin de preuve│
    └──────────────────┘  └─────────────────┘  └─────────────────┘
```

**La couture unique** est `spec → notes` : une spécification d'accord (hauteurs
et rôles harmoniques, sans octaves) entre, des notes MIDI sortent. Elle survit à
la refonte du moteur de voicing, qui se fait **derrière** elle sans toucher aux
frontends.

**Pourquoi trois frontends et pas un.** Concevoir un système de voicing est une
activité d'oreille : il faut écouter très souvent. La cible WASM rend la boucle
d'écoute instantanée dans un navigateur, alors que la boucle par le plugin est
compiler → bundler → recharger le DAW. Le `.wasm` mesuré fait **997 octets** et
n'importe aucune fonction hôte.

---

## 2. La stack, couche par couche

| couche | technologie | licence | pourquoi |
|---|---|---|---|
| Cœur harmonique | **Rust** 1.96+, edition 2021, `no_std` | — | Une erreur de mémoire ne compile pas ; compilable en WASM pour la boucle d'écoute ; le cœur fermé du produit est dans le langage le plus sûr des deux. |
| Frontière | **C ABI** (`extern "C"`, types POD) | — | Mesurée à **+0,64 ns/appel** en lien statique. Même couche pour les trois frontends, sans variante. |
| Plugin et UI | **C++17 / JUCE 9** | JUCE (voir §3) | Écosystème le plus documenté du domaine ; UI native mature ; standalone fourni ; AU disponible plus tard. |
| Format CLAP | **clap-juce-extensions** ou **clap-wrapper** | MIT | ⚠️ **JUCE ne produit pas de CLAP nativement.** |
| Build C++ | **CMake** + MSVC 14.44 (`vcvars64.bat`) | — | Voie recommandée par JUCE. MSVC et MSBuild sont déjà installés sur la machine de dev. |
| Build Rust | **cargo** | — | — |
| Validation | **clap-validator**, **pluginval** | MIT | Le premier est le seul validateur dont la couverture note on/off et événements MIDI est documentée. |

### Pourquoi pas Rust de bout en bout

`nice-plug` (le fork maintenu de `nih-plug`) est propre côté licence et fournit
params, state, smoothing, bundler et standalone. Mais son propre README écrit :
« *None of these options currently have good documentation for how to create
plugin GUIs* ». L'UI étant reconstruite de zéro et destinée à beaucoup changer,
la maturité de l'UI native pèse plus que l'unicité du langage.

### Pourquoi pas C++ de bout en bout

Aucun argument de latence ne le soutient. Mesuré sur la fonction de voicing :
Rust/LLVM **17,7 ns/appel** contre **24,4 ns** pour sa transcription C++/MSVC —
un écart de 6,7 ns, soit **six fois le coût de la frontière**. ⚠️ Ce chiffre
documente MSVC contre LLVM sur une fonction précise, sans LTCG ni PGO côté
MSVC ; ce n'est pas « Rust est plus rapide que C++ ». Il établit seulement que
la latence ne départage pas.

---

## 3. Licence JUCE — coût et pièges

Vérifié le 2026-07-29 sur l'EULA elle-même, pas sur la page marketing.

| tier | plafond de revenu / financement | par développeur | à deux |
|---|---|---|---|
| **Starter** | ≤ **20 000 $** / 12 mois | **gratuit** | **0 $** |
| Indie | ≤ 300 000 $ | 40 $/mois **ou** 800 $ perpétuel | 80 $/mois ou 1 600 $ |
| Pro | illimité | 175 $/mois (**engagement 12 mois**) ou 3 500 $ perpétuel | 4 200 $/an |

- **Source fermée autorisée à tous les tiers**, Starter compris.
- **Aucun splash screen.** Le mécanisme a été supprimé du code en JUCE 8 : le
  fichier `juce_JUCESplashScreen.h` renvoie 404 au tag `8.0.9`, et un
  avertissement de compilation signale que le flag est ignoré. Aucune clause
  d'attribution visuelle dans l'EULA.
- **Une licence par développeur** touchant au code, prestataires compris. Deux
  personnes = deux sièges. Les machines de build et de test n'en consomment pas.
- ⚠️ **Le plafond porte sur le revenu de l'entité entière.** Pour une personne
  physique, c'est le revenu tiré de l'usage du framework. Pour une société,
  c'est « *the total revenue or funding received by the entity and all its
  Affiliates … from all sources, whether it be received in connection with the
  entity's use of the Framework or not, without offsets of any kind* ». **La
  forme juridique choisie pour se répartir les revenus change le tier à payer.**
- ⚠️ **Sur abonnement, cesser de payer oblige à cesser de distribuer**, sauf
  rachat en perpétuel.
- Une licence perpétuelle ne couvre **qu'une version majeure** (JUCE 9 → 10 est
  un upgrade, remise de 30 % pour les détenteurs antérieurs).
- L'alternative copyleft est **AGPLv3** depuis JUCE 8 (c'était GPLv3 avant).
  On ne la choisit pas.

### Pourquoi JUCE 9 et pas 8

Le SDK VST3 embarqué dans JUCE **8.0.9** est encore en double licence
propriétaire/GPLv3 et sa voie propriétaire exige « *a copy of the License
Agreement signed by Steinberg* ». Celui de JUCE **9** est **MIT**. Même prix,
même EULA — une formalité en moins.

⚠️ **Les modules ISC ont disparu.** En JUCE 7, `juce_core`, `juce_events`,
`juce_audio_basics` et `juce_audio_devices` étaient sous ISC. Cette phrase est
absente de `LICENSE.md` en 8 et 9 : **toute la bibliothèque est désormais sous le
même régime**.

---

## 4. Politique de licence — la contrainte absolue

**Aucune dépendance copyleft, même transitive.** Le produit est fermé et
commercial.

Licences autorisées : `MIT`, `Apache-2.0`, `ISC`, `BSD-2-Clause`,
`BSD-3-Clause`, `Unicode-3.0`, plus la licence commerciale JUCE.

**Interdits nommément**, avec la preuve :

| interdit | raison |
|---|---|
| `nih-plug` | Son README : « *any VST3 plugins built with NIH-plug need to be able to comply with the terms of the GPLv3 license* ». |
| `vst3-sys` | Son `license.md` est **GPL v3-or-later**. C'est la cause de la clause ci-dessus. |
| Cible **AAX** de JUCE | SDK Avid, propriétaire **ou GPLv3**. Ne pas activer. |
| Cible **ASIO** de JUCE | SDK Steinberg, propriétaire **ou GPLv3**. Ne pas activer. |
| `JUCE_USE_MP3AUDIOFORMAT` | Désactivé par défaut, et JUCE avertit lui-même : « *NOT guaranteed to be free from infringements of 3rd-party intellectual property* ». Laisser à 0. |

**Le garde-fou est mécanique, pas déclaratif** : `cargo deny check licenses`
tourne en CI et bloque. Il doit être prouvé capable de **refuser** avant d'être
cru — ajouter temporairement une dépendance copyleft, constater l'échec, la
retirer.

**Verrou de version** : SDK VST3 **≥ 3.8.0** (MIT). Un SDK 3.7.x replonge dans
le régime dual GPLv3/propriétaire, et **aucun garde-fou automatique ne
l'impose** — c'est au build de le fixer.

---

## 5. Dépendances

### Rust

| crate | rôle | dépendances | licence |
|---|---|---|---|
| `harmony` | le cœur | **aucune** | propriétaire (à nous) |
| `mid-export` | CLI `.mid` | `midi_file` | MIT/Apache |
| hôtes de test | exercer le C ABI | `libloading` | à valider par `cargo deny` |

**`crates/harmony` n'a aucune dépendance de production.** `no_std`, sans
`alloc`. Vérifié au spike : `dumpbin -imports` sur la DLL produite ne montre
**aucun `malloc`/`free`**.

### C++

JUCE 9 embarque ses dépendances ; toutes permissives sauf les trois cibles
optionnelles interdites au §4. Aucune dépendance LGPL ni GPL-seule.
`JUCE_WEB_BROWSER` reste à 0 : inutile ici, et c'est ce qui charge WebKitGTK
sous Linux.

---

## 6. Profils de build et pièges

Ces cinq points coûtent des heures si on les découvre en route. Tous constatés
au spike du 2026-07-28.

1. **Les profils Cargo vivent à la RACINE du workspace.** Dans le `Cargo.toml`
   d'un membre ils sont **silencieusement ignorés**, et l'erreur qui en résulte
   (`unwinding panics are not supported without std`) ne pointe pas vers la cause.
2. **`opt-level = 3`, jamais `"z"`.** Mesuré : `"z"` coûte **+12,7 ns/appel**,
   onze fois le coût de la frontière FFI. Le gain de 9,5 Ko ne vaut rien.
3. **La commande de test est `cargo test --features std`**, jamais `cargo test`
   nu. `no_std` + `cdylib` + `cargo test` sont mutuellement hostiles : le cdylib
   exige `panic = "abort"`, cargo force `unwind` sur le profil test et refuse un
   `[profile.test] panic` explicite. Une feature `std`, off par défaut, arbitre.
4. **Gater le `panic_handler` sur la feature, pas sur `cfg(test)`** — cargo
   construit aussi la lib normale pour les doctests.
5. **Git Bash mange les arguments `/flag` de MSVC.** Utiliser `dumpbin -exports`
   et non `/exports`, sinon `LNK1181`.

Profil release :

```toml
[profile.release]
opt-level = 3
lto = true
panic = "abort"
codegen-units = 1
```

⚠️ **Le `panic_handler` en `loop {}` est un piège différé** : dans un thread
audio c'est un freeze, dans un onglet c'est un onglet mort. Aujourd'hui c'est du
code mort — aucun chemin de panique, aucun `unwrap`, bornes vérifiées. Dès qu'un
`unwrap` entrera dans le cœur, il deviendra un bug de production silencieux.

---

## 7. Invariants du thread audio

Non négociables, et le point 3 est une promesse produit.

1. **Zéro allocation, zéro lock, zéro I/O** dans `process()` et tout ce qu'il
   appelle. Le buffer de sortie est **possédé par l'appelant**, sur la pile.
2. **Zéro panique.** Tout passe par `Result`, aucun `unwrap` dans le cœur.
3. **Toute note-on a son note-off garanti** — changement d'accord, arrêt du
   transport, déchargement du plugin. Testé, pas supposé.
4. **Les notes sont placées à leur offset d'échantillon exact** dans le buffer
   (`addEvent(msg, sampleOffset)`), jamais à 0. C'est ce que VST3
   (`Event::sampleOffset`) et CLAP (`header.time`) permettent, et ce qui
   distingue un placement précis d'un placement quantifié au buffer.

**Outillage de preuve** : `RealtimeSanitizer` (Clang ≥ 20, `-fsanitize=realtime`)
couvre allocations, syscalls, locks et exceptions côté C++, sous Windows. Côté
Rust, un check d'allocation au niveau du framework en builds debug ; l'équivalent
RTSan standalone **ne supporte pas Windows**.

---

## 8. Contraintes imposées par les hôtes

- **Le plugin expose un bus de sortie audio même inutilisé.** Live et Cakewalk
  refusent de charger un plugin MIDI-only ; le contournement est en dur dans
  l'exemple officiel de JUCE.
- Le plugin se charge **en position d'instrument**, pas en MIDI FX : Live n'a pas
  de slot MIDI-effect pour VST/AU.
- **Live n'achemine ni les CC ni le pitch bend émis en VST3.** Non réparable de
  notre côté.
- **Live fusionne tous les canaux MIDI** en routage inter-pistes.
- Cibles v1 : **Windows**, **VST3 + CLAP**. Pas de Linux (supprime la question
  LGPL de WebKitGTK), pas d'AAX, macOS et AU après.

---

## 9. Propriété de fichiers

Aucun mécanisme de verrouillage entre agents n'existe : la seule protection est
la disjonction déclarée à l'avance.

| zone | propriétaire |
|---|---|
| `crates/harmony/`, `fixtures/` | Antoine — `fixtures/` est la spécification du produit |
| `plugin/`, `hosts/`, `xtask/`, CI | Stéphane |
| `Cargo.toml` racine, `CMakeLists.txt` racine, `ARCHITECTURE.md`, `PRD.md`, `.claude/settings.json` | **partagés** — modifiés uniquement sur `main`, en commit dédié |

Une PR touchant `fixtures/` ne se merge jamais sans revue d'Antoine.

---

## 10. Non décidé

1. **Le moteur d'expression** — un moteur servant le jeu et l'export, ou deux
   chemins. Couture d'architecture : à trancher avant d'écrire le moteur.
2. **Lien statique ou dynamique** de la lib Rust dans le plugin. Le spike a
   mesuré les deux (+0,64 ns statique, +1,14 ns DLL) ; le statique supprime un
   fichier à déployer. Non tranché.
3. **`clap-juce-extensions` ou `clap-wrapper`** pour le CLAP. Les deux sont MIT.
4. **La forme juridique** de la collaboration — elle détermine le tier JUCE (§3).
5. **La répartition entre les deux développeurs** — non décidée au 2026-07-29.
   Personne n'a renoncé à quoi que ce soit ; à trancher avant la première vente.
