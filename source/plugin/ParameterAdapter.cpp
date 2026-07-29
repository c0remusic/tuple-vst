#include "ParameterAdapter.h"

#include <memory>
#include <vector>

namespace tuple::plugin {

juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    params.push_back (std::make_unique<juce::AudioParameterInt> (
        kKeyParamID, "Key", kKeyMin, kKeyMax, kKeyDefault));

    params.push_back (std::make_unique<juce::AudioParameterInt> (
        kScaleParamID, "Scale", kScaleMin, kScaleMax, kScaleDefault));

    params.push_back (std::make_unique<juce::AudioParameterInt> (
        kOctaveParamID, "Octave", kOctaveMin, kOctaveMax, kOctaveDefault));

    params.push_back (std::make_unique<juce::AudioParameterFloat> (
        kOpennessParamID, "Openness",
        juce::NormalisableRange<float> (kOpennessMin, kOpennessMax), kOpennessDefault));

    params.push_back (std::make_unique<juce::AudioParameterFloat> (
        kDensityParamID, "Density",
        juce::NormalisableRange<float> (kDensityMin, kDensityMax), kDensityDefault));

    // DAW-exposed as "register" (Params.h); the value lands in
    // EngineSettings::centre below, never a field called `register` (that
    // name is a reserved word in C++).
    params.push_back (std::make_unique<juce::AudioParameterFloat> (
        kRegisterParamID, "Register",
        juce::NormalisableRange<float> (kRegisterMin, kRegisterMax), kRegisterDefault));

    return { params.begin(), params.end() };
}

EngineSettings readSettings (const juce::AudioProcessorValueTreeState& apvts)
{
    EngineSettings settings {};

    settings.key        = static_cast<uint8_t> (apvts.getRawParameterValue (kKeyParamID)->load());
    settings.scaleIndex = static_cast<uint8_t> (apvts.getRawParameterValue (kScaleParamID)->load());
    settings.octave     = static_cast<int8_t>  (apvts.getRawParameterValue (kOctaveParamID)->load());
    settings.openness   = apvts.getRawParameterValue (kOpennessParamID)->load();
    settings.density    = apvts.getRawParameterValue (kDensityParamID)->load();
    settings.centre     = static_cast<uint8_t> (juce::roundToInt (
                               apvts.getRawParameterValue (kRegisterParamID)->load()));

    return settings;
}

} // namespace tuple::plugin
