#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

#include "ParameterAdapter.h"
#include "Params.h"

// Thread-audio note: nothing in this class allocates, locks, or throws inside
// processBlock() yet. Task 1 wires only the bare bus/format skeleton needed
// for a host to load the plugin; the real audio-thread invariants (note-off
// guarantees, fixed-size buffers) land in Task 5.
class TupleProcessor : public juce::AudioProcessor
{
public:
    TupleProcessor();
    ~TupleProcessor() override;

    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    void processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override;

    const juce::String getName() const override;
    bool acceptsMidi() const override;
    bool producesMidi() const override;
    bool isMidiEffect() const override;
    double getTailLengthSeconds() const override;

    int getNumPrograms() override;
    int getCurrentProgram() override;
    void setCurrentProgram (int index) override;
    const juce::String getProgramName (int index) override;
    void changeProgramName (int index, const juce::String& newName) override;

    void getStateInformation (juce::MemoryBlock& destData) override;
    void setStateInformation (const void* data, int sizeInBytes) override;

    // The six parameters (Task 4, ARCHITECTURE.md §5 bis), built once here
    // via ParameterAdapter::createParameterLayout() — see ParameterAdapter.h
    // for why this is the only JUCE-typed parameter surface in the codebase.
    // Public: a future editor attaches sliders/combo boxes directly to it.
    juce::AudioProcessorValueTreeState apvts;

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TupleProcessor)
};
