#include "BuildGrid.h"

#include "../domain/Scale.h"

namespace tuple::app {

namespace {

using tuple::domain::ChordSpec;
using tuple::domain::Role;

// The fixed catalogue of kChordTypes chord-quality templates, root-relative
// (semitones from 0), independent of the current scale — the row axis of the
// grid (PRD.md §6, "Lignes : les types d'accord"). Neither PRD.md nor
// ARCHITECTURE.md enumerates a definitive 12-entry list yet (unlike the six
// plugin parameters or the six voicing families, which ARE frozen) — this is
// a deliberately naive placeholder in the same spirit as Voicing.h's
// realize(): "not musical — it is correct and deterministic". Four standard
// triad qualities, the two sus forms, and six standard seventh-chord
// qualities, built only from roles ChordTone already has (there is no
// "Sixth" role yet, so 6th chords are out of scope until domain/ grows one —
// that decision belongs to Antoine, domain/'s owner per ARCHITECTURE.md §5).
ChordSpec chordType (uint8_t root, uint8_t typeIndex)
{
    switch (typeIndex)
    {
        case 0:  return *ChordSpec::make (root, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth } });                        // major triad
        case 1:  return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 7, Role::Fifth } });                        // minor triad
        case 2:  return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 6, Role::Fifth } });                        // diminished triad
        case 3:  return *ChordSpec::make (root, { { 0, Role::Root }, { 4, Role::Third }, { 8, Role::Fifth } });                        // augmented triad
        case 4:  return *ChordSpec::make (root, { { 0, Role::Root }, { 2, Role::Sus },   { 7, Role::Fifth } });                        // sus2
        case 5:  return *ChordSpec::make (root, { { 0, Role::Root }, { 5, Role::Sus },   { 7, Role::Fifth } });                        // sus4
        case 6:  return *ChordSpec::make (root, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth }, { 10, Role::Seventh } }); // dominant 7th
        case 7:  return *ChordSpec::make (root, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth }, { 11, Role::Seventh } }); // major 7th
        case 8:  return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 7, Role::Fifth }, { 10, Role::Seventh } }); // minor 7th
        case 9:  return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 6, Role::Fifth }, { 9,  Role::Seventh } }); // diminished 7th
        case 10: return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 6, Role::Fifth }, { 10, Role::Seventh } }); // half-diminished 7th (m7b5)
        default: return *ChordSpec::make (root, { { 0, Role::Root }, { 3, Role::Third }, { 7, Role::Fifth }, { 11, Role::Seventh } }); // minor-major 7th (typeIndex == 11)
    }
}

} // namespace

Grid buildGrid (uint8_t key, uint8_t scaleIndex)
{
    using tuple::domain::intervalsFor;
    using tuple::domain::isValidScaleIndex;
    using tuple::domain::Scale;

    // isValidScaleIndex + intervalsFor (Scale.h) are the domain's own
    // vocabulary for "which scale, and what does it sound like" — using raw
    // uint8_t arithmetic here instead would leave them unconsumed dead code
    // (Task 2 review note) and would silently duplicate the scale-degree
    // catalogue this function has no business owning a second copy of.
    // isValidScaleIndex rejects the invalid; on rejection, fall back to
    // Scale::Major rather than producing a cell with an undefined interval.
    const uint8_t safeScaleIndex = isValidScaleIndex (scaleIndex) ? scaleIndex : 0;
    const auto intervals = intervalsFor (static_cast<Scale> (safeScaleIndex));

    // Any uint8_t is accepted as a key: wrap into a pitch class rather than
    // rejecting, since every value this produces is still exercised through
    // the same modulo arithmetic below.
    const uint8_t tonic = static_cast<uint8_t> (key % 12);

    Grid grid {};
    grid.count = 0;

    // Diatonic region: every (degree, chord-quality) pair is a cell — this is
    // exactly kDegrees * kChordTypes, the first term of kMaxGridCells.
    for (uint8_t degree = 0; degree < kDegrees; ++degree)
    {
        const uint8_t root = static_cast<uint8_t> ((tonic + intervals[degree]) % 12);
        for (uint8_t type = 0; type < kChordTypes; ++type)
            grid.cells[grid.count++] = GridCell { chordType (root, type), degree, false };
    }

    // Borrowed region: one cell per chromatic pitch class transposed to
    // `key`, all using the major-triad template (chordType(root, 0)) — a
    // deliberately naive placeholder standing in for real modal-interchange
    // logic (domain/ is Antoine's to refine, ARCHITECTURE.md §5). `degree`
    // here holds the pitch-class slot index (0..11), not a Degree value:
    // a borrowed chord has no diatonic degree.
    for (uint8_t slot = 0; slot < kBorrowedSlots; ++slot)
    {
        const uint8_t root = static_cast<uint8_t> ((tonic + slot) % 12);
        grid.cells[grid.count++] = GridCell { chordType (root, 0), slot, true };
    }

    return grid;
}

} // namespace tuple::app
