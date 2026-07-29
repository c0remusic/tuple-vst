#include "PlayChord.h"

#include "ReleaseAll.h"

namespace tuple::app {

using tuple::domain::NoteEvent;

NoteBatch playChord (const ChordRequest& request, const NoteBatch& sounding)
{
    // The outgoing chord's note-offs come first, via releaseAll — the same
    // pure function the other three note-off triggers use (ARCHITECTURE.md
    // §6 invariant 3). One shared implementation for "release everything in
    // this batch" means there is exactly one place that can forget to emit a
    // note-off, not two.
    NoteBatch result = releaseAll (sounding, request.sampleOffset);

    // Then the incoming chord's note-ons, from the Task 3 seam
    // (domain::realize) — this function never reimplements voicing logic.
    const auto realized = tuple::domain::realize (request.spec, request.family, request.settings);
    for (uint8_t i = 0; i < realized.count && result.count < kMaxNoteBatch; ++i)
    {
        result.events[result.count++] = NoteEvent { realized.notes[i], kDefaultVelocity, request.sampleOffset };
    }

    return result;
}

} // namespace tuple::app
