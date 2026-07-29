#pragma once

#include <array>
#include <cstdint>
#include <initializer_list>
#include <optional>

namespace tuple::domain {

// A tone's harmonic FUNCTION, not just its pitch. Rootless voicings must find
// "the Root" and remove it; Drop voicings must find a specific voice by name
// and move it down an octave. Neither family is implementable against a bag
// of bare integers — this is why ChordTone carries `role` instead of just a
// semitone offset (Task 2 rationale, docs/plans/2026-07-29-phase-0-squelette.md).
enum class Role : uint8_t {
    Root = 0,
    Third,
    Fifth,
    Seventh,
    Ninth,
    Eleventh,
    Thirteenth,
    Sus
};

// One chord tone: its distance in semitones from the chord's root (0..11,
// not yet placed in any octave), and the harmonic role it plays.
struct ChordTone {
    uint8_t semitones;
    Role role;
};

inline constexpr uint8_t kMaxChordTones = 6;

// A chord specification: a root pitch class plus up to six chord tones,
// still octave-less (ARCHITECTURE.md §1: "la couture reste spec -> notes").
// Fixed-size, no heap allocation — this type crosses into the app/ and
// plugin/ layers as a plain stack value (Task 3, Task 5).
struct ChordSpec {
    uint8_t rootPc;
    std::array<ChordTone, kMaxChordTones> tones;
    uint8_t count;

    // Validates and builds a ChordSpec. Returns std::nullopt if:
    //   - rootPc > 11 (not a pitch class), or
    //   - the tone list is empty, or has more than kMaxChordTones entries.
    // Tone order is preserved exactly as given: callers rely on the role at
    // a given index staying where they put it (Task 2 Step 1 test).
    static std::optional<ChordSpec> make (uint8_t rootPc,
                                           std::initializer_list<ChordTone> tones);
};

// The domain's readable state (ARCHITECTURE.md §5 bis, "une contrainte de
// forme sur la couche domaine"). The current scale and chord are exposed
// here rather than kept as an internal detail of the voicing engine — this
// is what would let a future melodic-guidance feature (Tupline) read the
// harmonic context without reaching into that engine.
struct HarmonicContext {
    uint8_t key;
    uint8_t scaleIndex;
    ChordSpec current;
};

} // namespace tuple::domain
