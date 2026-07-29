#include "PluginProcessor.h"
#include "PluginEditor.h"

namespace {

// juce_MidiBuffer.cpp's addEvent() stores each event as int32 sampleNumber +
// uint16 dataSize + the raw MIDI bytes (4 + 2 + N). Every event this plugin
// emits is a 3-byte note-on/note-off, i.e. 9 bytes/event; round up with
// headroom so this stays correct even if the MIDI messages emitted here ever
// grow past 3 raw bytes.
constexpr size_t kBytesPerNoteEvent = 16;
constexpr size_t kOutgoingBufferReserveBytes =
    (size_t) tuple::app::kMaxNoteBatch * kBytesPerNoteEvent;

} // namespace

// The fake output bus is not decorative: Live and Cakewalk refuse to load a
// MIDI-only plugin at all. See Global Constraints > "Contraintes d'hôte".
TupleProcessor::TupleProcessor()
    : AudioProcessor (BusesProperties()
        .withOutput ("Out", juce::AudioChannelSet::stereo(), true)),
      apvts (*this, nullptr, "PARAMETERS", tuple::plugin::createParameterLayout())
{
}

TupleProcessor::~TupleProcessor()
{
    // Trigger 4 of 4 (ARCHITECTURE.md §6 invariant 3, Task 5): plugin
    // destruction. There is no host MIDI buffer left to write into at this
    // point, so no note-off is actually emitted here — calling releaseAll()
    // and discarding its result would do nothing beyond what the assignment
    // below already does. What this site guarantees is that the object
    // never claims a note is still sounding once it is gone. The trigger's
    // note-off ACCOUNTING is what tests/noteoff_tests.cpp exercises, by
    // calling the pure releaseAll() directly with fabricated state ("Trigger
    // 4: destruction du plugin") — that test does not, and cannot, invoke
    // this destructor.
    sounding.count = 0;
}

void TupleProcessor::prepareToPlay (double /*sampleRate*/, int /*samplesPerBlock*/)
{
    // Global Constraints "buffers de taille fixe alloués dans prepareToPlay":
    // reserve processBlock()'s outgoing-MIDI scratch buffer here, once, off
    // the audio thread, so its addEvent() calls never grow it.
    outgoingBuffer.ensureSize (kOutgoingBufferReserveBytes);
}

void TupleProcessor::releaseResources()
{
    // Trigger 3 of 4 (ARCHITECTURE.md §6 invariant 3, Task 5). Same rationale
    // as ~TupleProcessor() above: no host MIDI buffer exists at this call
    // site, so there is nothing for releaseAll() to hand off to — clearing
    // the count is the entire effect.
    sounding.count = 0;
}

void TupleProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    // This device produces MIDI, not audio (Global Constraints: fake output
    // bus only satisfies hosts that refuse a MIDI-only plugin).
    buffer.clear();

    // Trigger 2 of 4 (ARCHITECTURE.md §6 invariant 3, Task 5): transport
    // stop. Compared against the PREVIOUS block's state so this fires once,
    // on the falling edge, not on every block the transport happens to be
    // stopped.
    bool isPlayingNow = false;
    if (auto* currentPlayHead = getPlayHead())
    {
        if (const auto position = currentPlayHead->getPosition())
            isPlayingNow = position->getIsPlaying();
    }

    // The mapping from incoming MIDI / mouse clicks to a ChordRequest
    // (ARCHITECTURE.md §5 bis "Le declenchement") is not yet decided — Task 5
    // wires only the note-off guarantee, not chord triggering. The incoming
    // buffer is therefore not forwarded: only what THIS device itself
    // produces (here, transport-stop releases) is written out.
    //
    // outgoingBuffer is NOT rebuilt here: it is the fixed-size member
    // reserved once in prepareToPlay() (Global Constraints, see its
    // declaration in PluginProcessor.h). clear() is Array::clearQuick() —
    // it resets the event count without freeing the reserved storage, so
    // the emit() call below never reallocates. Caveat, named rather than
    // hidden: swapWith() at the end of this function exchanges storage with
    // the host's midiMessages buffer, so from the NEXT block on this member
    // holds whatever capacity that buffer had — prepareToPlay()'s reserve
    // only strictly guarantees the first block after it runs. Closing that
    // gap fully would mean never handing our storage to the host at all,
    // which is a larger redesign than this correction's scope; the actual
    // proof point for zero-allocation, per Global Constraints, is
    // RealtimeSanitizer, not this comment.
    outgoingBuffer.clear();

    // The falling-edge decision itself lives in tuple::app::decideTransportStop
    // (source/app/TransportStop.h) — a pure function, testable without a JUCE
    // host (tests/noteoff_tests.cpp, "Regression: front descendant sur un
    // bloc de 0 echantillon"). Regression fixed there and closed here: a
    // zero-sample block landing exactly on this edge has no valid sample to
    // place a note-off at (Global Constraints: never fabricate an offset on
    // an empty buffer) — the OLD code below still advanced `wasPlaying`
    // unconditionally in that case, which erased the edge forever instead of
    // merely delaying the release. `decideTransportStop` reports
    // advanceWasPlaying == false for exactly that case, so `wasPlaying` is
    // left untouched here and the very same edge is retried on the next
    // block.
    const auto stopDecision = tuple::app::decideTransportStop (
        wasPlaying, isPlayingNow, sounding.count, buffer.getNumSamples());

    if (stopDecision.shouldRelease)
    {
        // Global Constraints: "notes placées à leur offset d'échantillon
        // exact, jamais à 0". This trigger has no per-note timing of its own
        // to place events at (unlike a chord change driven by an incoming
        // MIDI event's own offset) — but it does have this block's actual
        // sample count, and the LAST valid sample in it is the latest, most
        // conservative real offset available: it defers the release for as
        // long as this callback allows, rather than defaulting to the start.
        const auto offSample = buffer.getNumSamples() - 1;
        const auto offBatch = tuple::app::releaseAll (sounding, offSample);
        tuple::plugin::emit (offBatch, outgoingBuffer);
        sounding.count = 0;
    }

    if (stopDecision.advanceWasPlaying)
        wasPlaying = isPlayingNow;

    midiMessages.swapWith (outgoingBuffer);
}

juce::AudioProcessorEditor* TupleProcessor::createEditor()
{
    return new TupleEditor (*this);
}

bool TupleProcessor::hasEditor() const
{
    return true;
}

const juce::String TupleProcessor::getName() const
{
    return JucePlugin_Name;
}

bool TupleProcessor::acceptsMidi() const
{
    return true;
}

bool TupleProcessor::producesMidi() const
{
    return true;
}

bool TupleProcessor::isMidiEffect() const
{
    return false;
}

double TupleProcessor::getTailLengthSeconds() const
{
    return 0.0;
}

int TupleProcessor::getNumPrograms()
{
    return 1;
}

int TupleProcessor::getCurrentProgram()
{
    return 0;
}

void TupleProcessor::setCurrentProgram (int /*index*/)
{
}

const juce::String TupleProcessor::getProgramName (int /*index*/)
{
    return {};
}

void TupleProcessor::changeProgramName (int /*index*/, const juce::String& /*newName*/)
{
}

void TupleProcessor::getStateInformation (juce::MemoryBlock& destData)
{
    if (auto xml = apvts.copyState().createXml())
        copyXmlToBinary (*xml, destData);
}

void TupleProcessor::setStateInformation (const void* data, int sizeInBytes)
{
    if (auto xml = getXmlFromBinary (data, sizeInBytes))
        if (xml->hasTagName (apvts.state.getType()))
            apvts.replaceState (juce::ValueTree::fromXml (*xml));
}

// This factory is the one symbol every JUCE plugin format wrapper (VST3,
// CLAP via clap-juce-extensions) calls to instantiate the processor.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new TupleProcessor();
}
