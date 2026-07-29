#include "TransportStop.h"

namespace tuple::app {

TransportStopDecision decideTransportStop (bool wasPlaying, bool isPlayingNow,
                                            uint8_t soundingCount, int numSamples) TUPLE_NONBLOCKING
{
    const bool fallingEdge = wasPlaying && ! isPlayingNow && soundingCount > 0;

    if (! fallingEdge)
        return { false, true };

    if (numSamples > 0)
        return { true, true };

    // Zero-sample block: no valid sample offset exists to place the note-off
    // at (Global Constraints: never fabricate an offset on an empty buffer).
    // Do NOT advance wasPlaying -- keep this exact falling edge armed so the
    // next block retries it, instead of losing the note-off for good.
    return { false, false };
}

} // namespace tuple::app
