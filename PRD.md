# PRD — Tuple VST

**Date : 2026-07-29.** Statut : cadrage validé en session, périmètre v1 arrêté.
Les points encore ouverts sont listés au § 10 et ne sont pas des oublis.

Ce document décrit **le QUOI** : comportement, contenu, cas limites, ce qui est
inacceptable. Le COMMENT technique vit dans `ARCHITECTURE.md` et dans le plan
d'implémentation.

---

## 1. Le produit

**Tuple VST est un plugin d'accords MIDI-only pour DAW, dont l'argument est la
qualité du voicing et du mouvement entre accords.**

Il produit des notes MIDI et rien d'autre : aucun son, aucun traitement audio.
L'instrument est choisi par le producteur, dans son DAW.

**Pour qui.** Producteurs et musiciens qui composent ou jouent des progressions
d'accords, sur un DAW autre qu'Ableton Live exclusivement — Reaper, Bitwig,
Cubase, Studio One, FL Studio, Logic 11+ — et sur Live pour ceux qui acceptent
son routage à deux pistes.

**Contre quoi.** Le concurrent dominant est Scaler 3 (99 $, ≈ 1,3–1,5 Go). Ses
trois reproches les plus documentés, de 2024 à 2026, décrivent le même produit :
interface surchargée (« *they just kept adding stuff without any vision or
direction for the UI* »), notes bloquées jamais corrigées depuis la version 2.8,
et CPU élevé. Tuple VST est construit en négatif de ces trois points.

**Le trou dans le marché.** Aucun plugin commercial ne se positionne sur la
qualité du voicing et du voice leading — vérifié par recherche large le
2026-07-28. Partout, le voice leading est une fonctionnalité parmi d'autres.

---

## 2. Décisions cadres

| # | Décision |
|---|---|
| D1 | Produit **fermé et commercial**, distinct de Tuple (le device Max for Live, qui reste MIT et gratuit). |
| D2 | Le **device M4L reste gelé harmoniquement** : le nouveau moteur de voicing est exclusif au plugin. |
| D3 | Le corpus de cas (`fixtures/`) est **la spécification** du comportement harmonique. On ne modifie jamais un cas pour faire passer un test. |
| D4 | Périmètre : **voicing + progression/arrangement**. Ni banque de sons, ni hosting de plugins, ni détection audio, ni générateur de mélodie. |
| D5 | **L'UI est reconstruite de zéro**, libérée des contraintes de taille du format Max for Live. |
| D6 | La **grille reste la base du layout**. |

---

## 3. Principes non négociables

Hérités de Tuple, et ils survivent au portage :

1. **La grille est la fonctionnalité principale.** Elle affiche le maximum
   d'accords valides pour la tonalité et la gamme choisies.
2. **Aucun accord n'est caché derrière une page ou un assistant.** Les accords
   empruntés restent dans la grille principale.
3. **L'interface reste orientée performance** — pensée pour être jouée, pas
   seulement consultée.
4. **La basse est jouée par un instrument séparé.** Le plugin sort l'accord
   seul. Chaque voicing est un accord cohérent tenant sur une main, tonique en
   registre — pas de sub-bass isolé, pas d'écart de deux octaves. Seul le mode
   `piano` fait exception, il est délibérément à deux mains.
5. **Le mode avancé révèle des réglages, jamais il ne cache des accords.**

Nouveaux, propres au plugin :

6. **Toute note-on a son note-off garanti** — au changement d'accord, à l'arrêt
   du transport, au déchargement du plugin. C'est le bug ouvert depuis 2020 chez
   le concurrent ; ici c'est une promesse testée, pas une intention.
7. **Le résultat est déterministe.** Mêmes entrées, mêmes notes. C'est ce qui
   rend le corpus de cas possible.

---

## 4. Le modèle harmonique : deux axes

C'est la décision structurante du produit.

Scaler expose cinq notions dans sa « Colors Page » — substitutions, inversions,
extensions, variations, harmonie parallèle — qui se recouvrent, au point que ses
propres utilisateurs le lui reprochent : la page « *mixes concepts of chord
extensions / tensions […] along with the voicings, which are two fundamentally
different concepts* », jugée « *not really conducive to learning* ». Vérification
faite, leurs extensions sont un **sous-ensemble** de leurs variations, pas une
catégorie sœur.

Tuple VST n'a que **deux axes**, nommés et séparés :

### Axe 1 — QUEL accord

Ce qui change les hauteurs de notes (pitch classes) de l'accord.

- **Variation** — un autre accord bâti sur **le même degré**, avec une qualité
  différente : `I → Imaj7 → I6 → Isus4`. La fondamentale ne change pas.
- **Extension** — cas particulier de variation : empilement de tierces
  (7, 9, 11, 13). Nommé à part parce que c'est le geste le plus fréquent, mais
  il vit sur le même axe.
- **Substitution** — un accord **différent**, autre fondamentale, remplaçant le
  premier dans la même fonction harmonique (tonique / sous-dominante /
  dominante). C'est le seul des trois qui change de fondamentale.

### Axe 2 — COMMENT il est disposé

Ce qui change la répartition des mêmes hauteurs sur le registre.

- **Type de voicing** — la distribution des notes. Familles : serré, ouvert,
  drop, rootless, quartal, deux mains. Tuple en compte déjà 28 nommés.
- **Inversion** — quelle note est à la basse, à hauteurs identiques. Règle
  arrêtée : **la notation slash est la vérité de la basse** (`C/E` = mi à la
  basse).

### Pourquoi deux et pas cinq

Un utilisateur qui cherche « un accord plus riche » agit sur l'axe 1. Un
utilisateur qui trouve que « ça sonne mal placé » agit sur l'axe 2. Ce sont deux
intentions distinctes ; les mélanger dans une même page est exactement l'erreur
reprochée au concurrent.

---

## 5. Le moteur de voicing automatique

**Le moteur décide sur les deux axes ; l'utilisateur pose un caractère global et
peut forcer accord par accord.**

### 5.1 Caractère global

Un réglage unique, appliqué à toute la grille, qui contraint le moteur sans le
piloter. Il exprime une intention musicale, pas un algorithme :

- **Ouverture** — de serré à large.
- **Densité** — nombre de notes, du triadique à l'étendu.
- **Registre** — le centre autour duquel le moteur place les accords.

Le moteur choisit, pour chaque accord, le voicing et l'inversion qui respectent
ce caractère **et** qui minimisent le mouvement depuis l'accord précédent.

### 5.2 Override par accord

Sur n'importe quelle cellule, l'utilisateur peut forcer un voicing, une
inversion, une variation ou une extension. Le forçage **persiste** et l'auto
cesse d'agir sur cette cellule.

Exigences :
- Un accord forcé doit être **visuellement distinguable** d'un accord automatique.
- Le forçage doit être **annulable** — retour à l'auto en un geste.
- L'auto des accords voisins continue de tenir compte de l'accord forcé pour son
  voice leading.

### 5.3 Voice leading

Le mouvement entre accords successifs est la seconde moitié du moteur. Modes
existants, conservés : **ANCHOR** (ancre le registre) et **FLOW** (privilégie le
mouvement minimal). Le voice leading s'applique aussi bien aux accords
automatiques qu'aux accords forcés.

---

## 6. La grille

- Colonnes : les sept degrés de la gamme + les accords empruntés.
- Lignes : les types d'accord.
- Tout est visible simultanément. Aucun accord derrière un menu.
- Le codage couleur des degrés est conservé, avec ses logiques alternatives
  (spectre, fonction, tension, quintes, qualité).
- La grille est jouable à la souris **et** au clavier MIDI.

**Contrôles de tonalité** : tonalité, gamme. **Contrôles de style** : octave,
caractère global (§ 5.1), mode de voice leading.

---

## 7. Progression

Le tiroir de progression est conservé et fait partie du périmètre v1.

- **Capture** — ajouter l'accord joué à la progression.
- **Réordonnancement** — glisser pour changer l'ordre.
- **Écoute** — rejouer la progression.
- **Inversion par étape** — chaque accord de la progression porte sa propre
  inversion.
- **Export MIDI** — écrire la progression en fichier `.mid`.

**Exigence de qualité sur l'export, et c'est un point de différenciation.** Le
reproche fait à Scaler depuis 2018 et toujours d'actualité en 2026 est que son
export produit des blocs plats : « *MIDI velocity and expression on export are
basic and need tidying in your DAW* ». Chez eux, jouer et exporter sont deux
chemins différents. Ici, **ce qui est exporté doit être ce qui a été entendu.**

---

## 8. Sortie MIDI et réalité des DAW

Contraintes établies, non négociables parce qu'elles viennent des hôtes :

- Le plugin se charge **en position d'instrument** et expose un bus audio même
  inutilisé — Live et Cakewalk refusent sinon de le charger.
- **Live n'achemine ni les CC ni le pitch bend émis en VST3.** Le passthrough
  d'expression du device M4L ne peut pas fonctionner sous Live en VST3. À dire
  dans la documentation plutôt que de laisser l'utilisateur le découvrir.
- **Live fusionne tous les canaux MIDI** en routage inter-pistes.
- Hôtes où le routage est direct : **Reaper, Bitwig** (plugin et instrument sur
  la même piste), **Cubase/Studio One** (routage d'entrée dédié), **Logic 11+**
  (slot MIDI FX).
- Un **guide de routage par DAW** fait partie du produit livré, pas de la
  documentation optionnelle. Le concurrent en publie onze pages.

**Option secondaire, à trancher (§ 10)** : une sortie vers un port MIDI système
(port virtuel) pour contourner le routage. Répond à une demande ouverte et non
satisfaite chez le concurrent, mais dégrade la précision de placement des notes —
donc à proposer explicitement comme un compromis, jamais par défaut.

---

## 9. Hors périmètre, et pourquoi

Chaque exclusion est adossée à un reproche documenté fait au concurrent.

| Exclu | Raison |
|---|---|
| Banque de sons interne | Source principale du poids (≈ 1,3–1,5 Go), et reprochée en soi : « *the internal sound engine still leans toward basic General MIDI-style sounds* ». |
| Hosting de plugins VST/AU | N'existe chez le concurrent que pour compenser sa banque de sons faible. |
| Détection d'accords depuis l'audio | Source du reproche CPU le plus chiffré : 126 % de charge mesurée. |
| Générateur de mélodie / arpèges / patterns | C'est un autre produit. L'ajouter dilue « le voicing est LE produit ». |
| Linux (v1) | Supprime la seule question juridique restante sur la pile UI. |
| AAX / Pro Tools (v1) | Exige un compte Avid, une clé iLok et une adhésion supposant un produit déjà en vente. |
| macOS et AU (v1) | Après la v1 Windows. |

---

## 10. Questions ouvertes

Ces points ne sont pas tranchés. Ils ne bloquent pas la fondation technique,
mais chacun bloque une tranche fonctionnelle.

1. **Le moteur d'expression** — humanize, strum, vélocité. Un seul moteur
   servant le jeu temps réel **et** l'export, ou deux chemins séparés ? C'est
   une couture d'architecture : à décider avant d'écrire le moteur, pas après.
   Le § 7 exige déjà que l'export corresponde à ce qui est entendu, ce qui
   penche vers un moteur unique.
2. **Sortie vers port MIDI virtuel** (§ 8) — dans le périmètre v1 ou pas.
3. **Prix.** Zone déduite du marché : **59 à 79 $**. Le segment se concentre
   entre 39 et 99 $, le concurrent est à 99 $ avec un plancher de solde vérifié
   à 29 $, et le gratuit est crédible (Ripchord open source, Ableton Expressive
   Chords livré avec Live 12.2).
4. **La répartition entre les deux développeurs** — part, forfait, ou autre.
   À écrire avant la première ligne de code produit.
5. **Le détail du caractère global** (§ 5.1) — trois curseurs, des préréglages
   nommés, ou les deux. Décision d'interface, à prendre sur maquette.

---

## 11. Le device Max for Live comme référence fonctionnelle

**Tuple VST repart de zéro. Aucun code du device n'est repris par défaut** ;
toute reprise éventuelle serait une décision explicite, pas un présupposé.

Ce qui suit est un **inventaire de ce que le device fait**, du point de vue de
l'utilisateur — utile pour décider ce qu'on garde, ce qu'on jette et ce qui
manque. Ce n'est pas une liste de fichiers à porter.

**Ce qu'on garde comme idée :**
- La grille de tous les accords de la gamme, empruntés compris, tout visible.
- La notion de spécification d'accord — hauteurs et rôles harmoniques, sans
  octaves — comme point d'articulation entre « quel accord » et « comment il
  sonne ».
- Les substitutions par fonction harmonique.
- Les inversions, avec la règle « slash = vérité de la basse ».
- Les suggestions d'accord suivant.
- Le tiroir de progression.

**Ce qu'on jette :**
- Les **28 types de voicing nommés**. Remplacés par six familles (voir §4), et
  les noms évoquant un genre musical disparaissent.
- Le moteur de voicing lui-même, entièrement remplacé.
- Tout ce qui dépend de Live : synchronisation de gamme, écriture dans un clip,
  intégration Push, architecture à deux fenêtres.

**Ce qui manque et qu'il faudra concevoir :**
- Le nouveau moteur de voicing automatique et ses réglages de caractère.
- Le forçage par accord et sa persistance.
- L'expression à l'export (§7).
