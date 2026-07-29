#pragma once

#include <array>
#include <cstdint>

#include "../domain/ChordSpec.h"
#include "../domain/NoteEvent.h"
#include "../domain/Voicing.h"
#include "../domain/VoicingFamily.h"

namespace tuple::app {

// One request to play a chord: what to voice, how, and at which sample
// offset within the current audio-thread callback the resulting MIDI events
// should land (ARCHITECTURE.md §6 invariant 4 — never offset 0 by default).
struct ChordRequest
{
    tuple::domain::ChordSpec spec;
    tuple::domain::VoicingFamily family;
    tuple::domain::VoicingSettings settings;
    int sampleOffset;
};

// kMaxRealizedNotes (Voicing.h, 8) note-offs for the outgoing chord, plus up
// to kMaxRealizedNotes note-ons for the incoming one: 16 is not a magic
// number, it is that sum.
inline constexpr uint8_t kMaxNoteBatch = 16;

// A fixed-size batch of MIDI-shaped note events, returned by copy — no heap,
// safe to build and consume from the audio thread (Global Constraints,
// "la regle la plus facile a casser").
//
// Convention: velocity == 0 marks a note-OFF (the same convention real MIDI
// running-status "note on, velocity 0" uses); velocity > 0 marks a note-ON.
// This is what lets a single NoteBatch carry both kinds of event without a
// separate discriminant field.
struct NoteBatch
{
    std::array<tuple::domain::NoteEvent, kMaxNoteBatch> events;
    uint8_t count;
};

// Phase 0 does not expose velocity as one of the six automatable parameters
// (ARCHITECTURE.md §5 bis) — every note-on this phase emits uses this fixed
// value.
inline constexpr uint8_t kDefaultVelocity = 100;

// Releases every note in `sounding` (note-off, velocity 0) and realizes
// `request` into note-ons (via the Task 3 seam, domain::realize), all at
// `request.sampleOffset`. Returns BOTH sets in the SAME NoteBatch: the
// outgoing chord's note-offs first, the incoming chord's note-ons after —
// this is what makes "every note-on has a note-off" testable without a host
// (Task 5, docs/plans/2026-07-29-phase-0-squelette.md).
NoteBatch playChord (const ChordRequest& request, const NoteBatch& sounding);

} // namespace tuple::app
