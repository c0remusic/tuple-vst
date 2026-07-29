#pragma once

#include "PlayChord.h" // NoteBatch

namespace tuple::app {

// Releases every note in `sounding` (note-off, velocity 0) at `sampleOffset`.
// The shared half of playChord()'s job, exposed on its own for the other
// three note-off triggers (ARCHITECTURE.md §6 invariant 3): transport stop,
// releaseResources, and plugin destruction — none of which involve playing a
// NEW chord.
NoteBatch releaseAll (const NoteBatch& sounding, int sampleOffset);

} // namespace tuple::app
