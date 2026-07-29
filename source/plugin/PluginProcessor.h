#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

#include "../app/PlayChord.h"   // tuple::app::NoteBatch
#include "../app/ReleaseAll.h"
#include "MidiEmitter.h"
#include "ParameterAdapter.h"
#include "Params.h"

// Thread-audio note: processBlock() below allocates nothing, locks nothing,
// throws nothing, and does no I/O (Global Constraints, ARCHITECTURE.md §6).
// `sounding` is the fixed-size audio-thread state Task 5 Step 6 asks for:
// no std::vector, no heap, just a tuple::app::NoteBatch value living on this
// object.
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
    // The audio-thread's fixed-size record of what is currently sounding
    // (Task 5, Global Constraints "buffers de taille fixe alloues dans
    // prepareToPlay" — trivially satisfied here since the type has no heap
    // storage to begin with). Read and written only from processBlock(),
    // releaseResources(), and the destructor — the three plugin-layer sites
    // of the four note-off triggers (the fourth, chord change, is playChord's
    // own job and does not need a separate site here).
    tuple::app::NoteBatch sounding {};

    // Tracked so processBlock() can detect the transport EDGE (was playing,
    // now stopped) rather than releasing every block the transport happens
    // to be stopped — see processBlock()'s definition.
    bool wasPlaying = false;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TupleProcessor)
};
