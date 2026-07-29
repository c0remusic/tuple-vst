#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

class TupleProcessor;

// Deliberately empty (Global Constraints / Hors périmètre: "L'UI définitive
// est reconstruite de zéro"). This is only the minimal editor a host needs
// to be able to open a window at all.
class TupleEditor : public juce::AudioProcessorEditor
{
public:
    explicit TupleEditor (TupleProcessor& processorToEdit);
    ~TupleEditor() override;

    void paint (juce::Graphics& g) override;
    void resized() override;

private:
    TupleProcessor& processor;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TupleEditor)
};
