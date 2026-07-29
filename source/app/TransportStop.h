#pragma once

#include <cstdint>
#include "../RealtimeAnnotations.h"

namespace tuple::app {

// The falling-edge decision for Trigger 2 (arret du transport,
// ARCHITECTURE.md Sec.6 invariant 3), extracted out of
// PluginProcessor::processBlock() so it is testable without instantiating
// JUCE (ARCHITECTURE.md Sec.1: domain/ and app/ compile standalone, no host).
// Pure function: no I/O, no allocation, no JUCE type, no side effect.
//
// Regression fixed here: a zero-sample block landing exactly on the falling
// edge (wasPlaying == true, isPlayingNow == false) has no valid sample to
// place a note-off at. The previous inline logic in processBlock() still
// advanced its wasPlaying flag unconditionally after that block, which
// permanently erased the edge: "wasPlaying && !isPlayingNow" could never be
// true again for that transport stop, so the note-off was not merely
// delayed, it was lost for good. The fix: only report the edge as consumed
// (advanceWasPlaying == true) when a release actually happened or when there
// was nothing to release in the first place — never when a release was due
// but could not be emitted.
struct TransportStopDecision
{
    // True: the caller must call releaseAll() now, at sample (numSamples - 1),
    // and clear its sounding state.
    bool shouldRelease;

    // True: the caller should advance its wasPlaying state to isPlayingNow.
    // False: leave wasPlaying UNCHANGED so the very same falling edge is
    // retried on the next block instead of being silently dropped.
    bool advanceWasPlaying;
};

// TUPLE_NONBLOCKING: called from TupleProcessor::processBlock, so it inherits
// the audio-thread contract. Annotating it is not paperwork -- without it,
// Clang reported this call as "cannot be inferred 'nonblocking' because it has
// no definition in this translation unit" (run 30469650838), i.e. the analysis
// stopped at our own boundary. With the annotation the compiler verifies the
// body instead of giving up at the declaration.
TransportStopDecision decideTransportStop (bool wasPlaying, bool isPlayingNow,
                                            uint8_t soundingCount, int numSamples) TUPLE_NONBLOCKING;

} // namespace tuple::app
