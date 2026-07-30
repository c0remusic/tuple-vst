#include "PluginProcessor.h"
#include "PluginEditor.h"

#if defined(TUPLE_RTSAN)
 #include <cstdlib>
#endif

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
#if defined(TUPLE_RTSAN)
    // Off the audio thread, once. See rtsanSabotage's declaration for why this
    // exists and what CI does with it.
    rtsanSabotage = (std::getenv ("TUPLE_RTSAN_SABOTAGE") != nullptr);
#endif
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

// TUPLE_NONBLOCKING is repeated here because it is part of the function TYPE:
// a definition without it would not match the declaration in the header.
void TupleProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) TUPLE_NONBLOCKING
{
#if defined(TUPLE_RTSAN)
    if (rtsanSabotage)
    {
        // Deliberate, opt-in, sanitizer-build-only violation: the planted
        // witness described at rtsanSabotage's declaration. RTSan must abort
        // here. The static -Wfunction-effects diagnostic is silenced for this
        // block ONLY — it would otherwise report a "finding" that is the whole
        // point of the code, drowning the real ones in the build-log summary
        // CI collects. Silencing the compile-time diagnostic does not touch
        // the runtime instrumentation (RealtimeAnnotations.h, point 2), which
        // is precisely what this block is here to exercise.
        #pragma clang diagnostic push
        #pragma clang diagnostic ignored "-Wfunction-effects"
        void* deliberate = std::malloc (16);
        // The barrier is load-bearing, not defensive. Without it this pair is
        // dead code -- LLVM removes a malloc() whose result is never observed
        // and is immediately free()d -- so at -O3 the witness evaporated and
        // the armed run exited 0 while every piece of instrumentation was
        // present and correct (measured on run 30469650838: PluginProcessor.cpp
        // compiled with -fsanitize=realtime AND -DTUPLE_RTSAN, the built plugin
        // referencing ___rtsan_realtime_enter, the host linking the runtime).
        // The RTSan self-test earlier in the same job never caught this because
        // it compiles unoptimised: a witness that only survives at -O0 does not
        // witness the Release build it is supposed to be guarding.
        asm volatile ("" : : "r" (deliberate) : "memory");
        std::free (deliberate);
        #pragma clang diagnostic pop
    }
#endif

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
    // the emit() call below never reallocates. The reserve holds for EVERY
    // block, not just the first: this function no longer hands its storage to
    // the host. It used to end on swapWith(), which exchanged buffers — the
    // member then carried whatever capacity the host's buffer happened to have,
    // so prepareToPlay()'s reserve only strictly covered the first block and
    // any later emit() could allocate on the audio thread. The comment that
    // stood here named that gap and judged closing it "a larger redesign";
    // it is two lines (see the end of this function). Audit 2026-07-30.
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

    // COPIE, jamais swapWith(). L'echange donnerait a outgoingBuffer la capacite
    // du buffer de l'hote, sans aucune garantie qu'elle atteigne la reserve de
    // prepareToPlay() — le prochain addEvent() de emit() pourrait alors allouer
    // DANS le thread audio, ce que ensureSize() existe precisement pour empecher.
    // Copier laisse la reserve du membre intacte, indefiniment.
    //
    // Ce que voit l'hote est identique: il recevait le contenu de outgoingBuffer,
    // il le recoit toujours. Seule difference, invisible dehors: outgoingBuffer
    // garde son propre contenu au lieu de recuperer l'ancien buffer d'entree —
    // sans effet, le clear() en tete de cette fonction l'efface au bloc suivant.
    //
    // addEvents(src, startSample, numSamples, sampleDeltaToAdd): numSamples < 0
    // prend TOUS les evenements a partir de startSample (juce_MidiBuffer.h:240-247,
    // verifie sur la copie vendored, pas de memoire).
    midiMessages.clear();
    midiMessages.addEvents (outgoingBuffer, 0, -1, 0);
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
    {
        if (xml->hasTagName (apvts.state.getType()))
        {
            apvts.replaceState (juce::ValueTree::fromXml (*xml));

            // apvts.replaceState() above changes each parameter's live value
            // directly, but does NOT notify the host — that is a SEPARATE
            // step, updateHostDisplay(), that every host-format wrapper
            // (VST3, CLAP via clap-juce-extensions) listens for through
            // juce::AudioProcessorListener::audioProcessorChanged() before it
            // will re-read parameter values on its own. Without this call,
            // a host that reloads a saved session (recreate the plugin,
            // setStateInformation with the old session data) ends up with
            // stale parameter values in its own UI/automation lanes even
            // though this processor's own apvts is correct — exactly the
            // clap-validator state-reproducibility-{basic,binary,buffered}
            // failure recorded in proof/task7-ci.md Step 4 ("these parameter
            // values changed without a rescan request"). programChanged is
            // the flag clap-juce-extensions' wrapper treats as "a preset was
            // loaded, rescan parameter VALUES" (see its audioProcessorChanged
            // override) — the correct, minimal flag here, since only VALUES
            // changed, not the parameters' names/ranges/count.
            updateHostDisplay (juce::AudioProcessor::ChangeDetails{}.withProgramChanged (true));
        }
    }
}

// This factory is the one symbol every JUCE plugin format wrapper (VST3,
// CLAP via clap-juce-extensions) calls to instantiate the processor.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new TupleProcessor();
}
