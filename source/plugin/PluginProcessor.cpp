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

TupleProcessor::~TupleProcessor() = default;

void TupleProcessor::prepareToPlay (double /*sampleRate*/, int /*samplesPerBlock*/)
{
}

void TupleProcessor::releaseResources()
{
}

void TupleProcessor::processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& /*midiMessages*/)
{
    // Skeleton only: no chord logic yet (Task 5). Silence is the honest
    // output of a plugin that produces MIDI, not audio.
    buffer.clear();
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
