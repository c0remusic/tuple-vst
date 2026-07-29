#pragma once

#include <array>
#include <cstdint>

#include "ChordSpec.h"
#include "VoicingFamily.h"

namespace tuple::domain {

// The three parameters that steer voicing (ARCHITECTURE.md §5 bis). `centre`
// is the C++ field for the DAW-exposed `register` parameter: `register` is a
// reserved word in C++, so the identifier the host sees and the field name
// here are deliberately different (Global Constraints, Task 4 wires this up
// for real). `centre` is expected to already be a valid MIDI note (0..127) —
// this struct does not validate, the same way it is not `realize()`'s job to
// clamp a caller's contract violation into meaning.
struct VoicingSettings {
    float openness;
    float density;
    uint8_t centre;
};

inline constexpr uint8_t kMaxRealizedNotes = 8;

// A realized chord: fixed-size, returned by copy. No std::vector, no
// allocation — this crosses into plugin/ and may be read from the audio
// thread (Global Constraints, "la regle la plus facile a casser").
struct RealizedChord {
    std::array<uint8_t, kMaxRealizedNotes> notes;
    uint8_t count;
};

// The spec -> notes seam (Task 3). Phase 0's implementation is deliberately
// naive: every chord tone is placed in the octave nearest `settings.centre`,
// and `family` applies one small, safe redistribution on top. It is not
// musical — it is correct and deterministic, behind the signature the real
// voicing engine will occupy later. `openness`/`density` are accepted for
// forward API stability; Phase 0 does not read them yet.
RealizedChord realize (const ChordSpec& spec, VoicingFamily family, const VoicingSettings& settings);

} // namespace tuple::domain
