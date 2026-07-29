#include "MidiEmitter.h"

namespace tuple::plugin {

void emit (const tuple::app::NoteBatch& batch, juce::MidiBuffer& buffer)
{
    for (uint8_t i = 0; i < batch.count; ++i)
    {
        const auto& event = batch.events[i];

        // Convention (MidiEmitter.h / NoteBatch): velocity == 0 is a
        // note-off, velocity > 0 is a note-on.
        const auto message = (event.velocity == 0)
            ? juce::MidiMessage::noteOff (1, event.pitch)
            : juce::MidiMessage::noteOn (1, event.pitch, event.velocity);

        // ARCHITECTURE.md §6 invariant 4: the event's OWN sample offset,
        // never 0.
        buffer.addEvent (message, event.sampleOffset);
    }
}

} // namespace tuple::plugin
