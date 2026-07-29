#include "ReleaseAll.h"

namespace tuple::app {

using tuple::domain::NoteEvent;

NoteBatch releaseAll (const NoteBatch& sounding, int sampleOffset)
{
    NoteBatch result {};
    result.count = 0;

    for (uint8_t i = 0; i < sounding.count && result.count < kMaxNoteBatch; ++i)
    {
        result.events[result.count++] = NoteEvent { sounding.events[i].pitch, 0, sampleOffset };
    }

    return result;
}

} // namespace tuple::app
