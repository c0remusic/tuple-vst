#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

#include "Params.h"

namespace tuple::plugin {

// The ONLY place a JUCE type touches parameter settings (Task 4, Global
// Constraints). PluginProcessor calls createParameterLayout() once, in its
// member-initialiser list, to build its AudioProcessorValueTreeState; any
// later reader of the current settings calls readSettings() and gets back a
// plain EngineSettings — never a juce::RangedAudioParameter, never the
// AudioProcessorValueTreeState itself.

// Declares exactly the six parameters (ARCHITECTURE.md §5 bis), under the
// stable IDs and ranges declared in Params.h. The list is definitive: do not
// add, remove, or rename a parameter here without a new decision recorded
// the same way ARCHITECTURE.md §5 bis was.
juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

// Reads the current value of each of the six parameters into a plain
// EngineSettings. Six atomic loads, no allocation, no lock — safe to call
// from the audio thread (Task 5 will call this once per block).
EngineSettings readSettings (const juce::AudioProcessorValueTreeState& apvts);

} // namespace tuple::plugin
