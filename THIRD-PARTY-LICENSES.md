# Licences tierces

Registre des licences des dépendances récupérées par `CMakeLists.txt`
(`FetchContent`). Complète `ARCHITECTURE.md` §3-4 (politique et pièges) : ce
fichier est le point de vérification factuel, l'autre le raisonnement.

## JUCE 9.0.0 (tag épinglé)

**Double licence** — commerciale (Raw Material Software) ou AGPLv3. Vérifié
sur pièce dans le code source vendored lui-même : chaque en-tête JUCE porte
les deux termes verbatim, par exemple
`build/_deps/juce-src/modules/juce_audio_processors_headless/format/juce_PluginFormatDefs.h`
après un premier `cmake -B build` (JUCE n'est pas commité — `build/` est
gitignored, mais le tag `9.0.0` étant épinglé, quiconque relance `cmake -B
build` obtient verbatim le même en-tête). Texte canonique :
<https://juce.com/legal/juce-9-licence/>.

**Choix retenu : licence commerciale, tier Starter.** L'AGPLv3 est copyleft —
exclue par la contrainte globale « aucune dépendance copyleft, même
transitive » (`docs/plans/2026-07-29-phase-0-squelette.md` § Global
Constraints). Le critère du tier Starter, tel que défini par l'EULA JUCE : le
revenu ou financement total reçu par l'entité et ses affiliés, toutes sources
confondues, sur les 12 derniers mois glissants, **≤ 20 000 $**. Voir le
tableau complet des tiers et leurs pièges dans `ARCHITECTURE.md` §3
(abonnement vs perpétuel, un siège par développeur, le plafond porte sur
l'entité entière).

**Ce que ce fichier NE certifie PAS** : l'inscription effective d'un compte
Raw Material Software sous ce tier est une démarche commerciale que fait
l'équipe elle-même, en dehors de ce dépôt — aucun fichier de code ne peut en
tenir lieu. Ce que ce fichier fixe, c'est le critère applicable et le
déclencheur de re-vérification : **si le revenu/financement de l'entité
dépasse 20 000 $ sur 12 mois glissants, réévaluer le tier avant la prochaine
release** (Indie ou Pro — voir `ARCHITECTURE.md` §3).

## clap-juce-extensions (SHA épinglé `54b3c3268ab6721a7afeef813c9e1ce43a3d0fcd`)

**MIT.** Vérifié via l'API de licence GitHub le 2026-07-29 sur le dépôt
`free-audio/clap-juce-extensions`. Le SHA épinglé est le commit `54b3c326`
(« Fix null termination of CLAP metadata strings (#179) »), un commit après
`26bab6be` (« JUCE 9 support (#178) », 2026-07-21) — confirmé via l'API
compare de GitHub le 2026-07-29 (`ahead_by: 1`). Voir le commentaire dans
`CMakeLists.txt` pour le pourquoi de l'épinglage sur un SHA plutôt qu'un tag.

Dépendance transitive : les headers CLAP (`free-audio/clap`,
`free-audio/clap-helpers`, sous-modules de clap-juce-extensions) — MIT
également (en-tête de licence visible dans chaque fichier sous
`build/_deps/clap_juce_extensions-src/clap-libs/`).

## Autres dépendances vendored par JUCE

Documenté dans `ARCHITECTURE.md` §4 : FLAC et Ogg Vorbis (BSD), HarfBuzz,
zlib, CHOC (ISC). Aucune dépendance LGPL ni GPL-seule. `JUCE_USE_MP3AUDIOFORMAT`
et `JUCE_WEB_BROWSER` restent à 0 (voir `CMakeLists.txt`), donc ni le module
MP3 de JUCE ni WebKitGTK ne sont jamais compilés ou liés.
