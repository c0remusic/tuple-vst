#include "PluginEditor.h"
#include "PluginProcessor.h"

TupleEditor::TupleEditor (TupleProcessor& processorToEdit)
    : AudioProcessorEditor (&processorToEdit), processor (processorToEdit)
{
    setSize (400, 300);
}

TupleEditor::~TupleEditor() = default;

void TupleEditor::paint (juce::Graphics& g)
{
    g.fillAll (getLookAndFeel().findColour (juce::ResizableWindow::backgroundColourId));
}

void TupleEditor::resized()
{
}
