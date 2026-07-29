#include "PluginProcessor.h"
#include "PluginEditor.h"

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
    // point — what IS guaranteed is that this object never claims a note is
    // still sounding once it is gone. releaseAll()'s pure return value is
    // what tests/noteoff_tests.cpp exercises for this exact trigger ("Trigger
    // 4: destruction du plugin").
    tuple::app::releaseAll (sounding, 0);
    sounding.count = 0;
}

void TupleProcessor::prepareToPlay (double /*sampleRate*/, int /*samplesPerBlock*/)
{
}

void TupleProcessor::releaseResources()
{
    // Trigger 3 of 4 (ARCHITECTURE.md §6 invariant 3, Task 5).
    tuple::app::releaseAll (sounding, 0);
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
    juce::MidiBuffer outgoing;

    if (wasPlaying && ! isPlayingNow && sounding.count > 0)
    {
        const auto offBatch = tuple::app::releaseAll (sounding, 0);
        tuple::plugin::emit (offBatch, outgoing);
        sounding.count = 0;
    }

    wasPlaying = isPlayingNow;

    midiMessages.swapWith (outgoing);
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
