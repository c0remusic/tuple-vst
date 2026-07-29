#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include "../app/PlayChord.h" // NoteBatch
#include "../RealtimeAnnotations.h"

namespace tuple::plugin {

// The ONE place a NoteBatch (app/, framework-free) becomes a
// juce::MidiBuffer (ARCHITECTURE.md §5: "MidiEmitter.h/.cpp NoteBatch ->
// juce::MidiBuffer"). Every event lands at ITS OWN sampleOffset
// (ARCHITECTURE.md §6 invariant 4) — never at 0. Convention (see NoteBatch):
// velocity == 0 is a note-off, velocity > 0 is a note-on. MIDI channel is
// always 1 — Phase 0 does not expose channel routing.
// TUPLE_NONBLOCKING: reached from processBlock. Note what this does NOT claim
// -- juce::MidiBuffer::addEvent() grows its storage if it has to, and that
// would be an audio-thread allocation. The annotation is exactly the assertion
// that it never has to here, because prepareToPlay() reserved the buffer up
// front (PluginProcessor.h, outgoingBuffer). Clang cannot check that from the
// declaration alone; RealtimeSanitizer checks it at run time, which is the
// point of putting the contract in the type.
void emit (const tuple::app::NoteBatch& batch, juce::MidiBuffer& buffer) TUPLE_NONBLOCKING;

} // namespace tuple::plugin
