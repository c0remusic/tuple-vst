#pragma once

#include <cstdint>

namespace tuple::domain {

// A single MIDI note event, placed at its exact sample offset within an
// audio-thread callback (ARCHITECTURE.md §6, invariant 4). This type is
// framework-free by construction (ARCHITECTURE.md §5): MidiEmitter (Task 5,
// source/plugin/) is the one place that turns it into a host-buffer entry,
// at that same sampleOffset.
struct NoteEvent {
    uint8_t pitch;
    uint8_t velocity;
    int sampleOffset;
};

} // namespace tuple::domain
