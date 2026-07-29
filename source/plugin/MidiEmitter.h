#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include "../app/PlayChord.h" // NoteBatch

namespace tuple::plugin {

// The ONE place a NoteBatch (app/, framework-free) becomes a
// juce::MidiBuffer (ARCHITECTURE.md §5: "MidiEmitter.h/.cpp NoteBatch ->
// juce::MidiBuffer"). Every event lands at ITS OWN sampleOffset
// (ARCHITECTURE.md §6 invariant 4) — never at 0. Convention (see NoteBatch):
// velocity == 0 is a note-off, velocity > 0 is a note-on. MIDI channel is
// always 1 — Phase 0 does not expose channel routing.
void emit (const tuple::app::NoteBatch& batch, juce::MidiBuffer& buffer);

} // namespace tuple::plugin
