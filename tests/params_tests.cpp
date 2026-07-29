// Params test binary (Task 4, docs/plans/2026-07-29-phase-0-squelette.md).
// Same self-contained runner style as tests/domain_tests.cpp and
// tests/voicing_tests.cpp ([PASS]/[FAIL] printf, exit code = failure count),
// but this one DOES need JUCE: ParameterAdapter is "the only place a JUCE
// type touches settings" (Global Constraints), and this binary is the thing
// that exercises that seam.
//
// Written and run BEFORE source/plugin/Params.h and
// source/plugin/ParameterAdapter.{h,cpp} exist. At this point the two
// #includes below point at nothing, so this binary is expected to fail to
// COMPILE (file not found) — that is the RED state (TDD, non-negociable per
// dispatch instructions; the plan's own Step numbering for this task lists
// "declare the layout" and "write ParameterAdapter" before "test", but the
// dispatch's method rules override that ordering).
//
// A minimal AudioProcessor stub (TestHostProcessor, below) hosts the APVTS:
// juce::AudioProcessorValueTreeState's constructor requires a live
// AudioProcessor to attach to. Using a tiny local stub instead of the real
// TupleProcessor keeps this test binary JUCE-audio-only (no juce_gui_basics,
// no PluginEditor) — same "fast loop" rationale CMakeLists.txt gives for
// DomainTests/VoicingTests, just one JUCE module deep instead of zero.

#include "../source/plugin/Params.h"
#include "../source/plugin/ParameterAdapter.h"

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_events/juce_events.h>

#include <cstdio>
#include <memory>
#include <string>

using tuple::plugin::EngineSettings;
using tuple::plugin::createParameterLayout;
using tuple::plugin::readSettings;

namespace {

int failures = 0;

void expectTrue (bool condition, const std::string& description)
{
    if (condition)
    {
        std::printf ("[PASS] %s\n", description.c_str());
    }
    else
    {
        std::printf ("[FAIL] %s\n", description.c_str());
        ++failures;
    }
}

void expectEqualInt (long long actual, long long expected, const std::string& description)
{
    if (actual == expected)
    {
        std::printf ("[PASS] %s\n", description.c_str());
    }
    else
    {
        std::printf ("[FAIL] %s (got %lld, expected %lld)\n",
                      description.c_str(), actual, expected);
        ++failures;
    }
}

void expectEqualFloat (float actual, float expected, const std::string& description)
{
    if (actual == expected)
    {
        std::printf ("[PASS] %s\n", description.c_str());
    }
    else
    {
        std::printf ("[FAIL] %s (got %f, expected %f)\n",
                      description.c_str(), (double) actual, (double) expected);
        ++failures;
    }
}

// A minimal juce::AudioProcessor: every pure virtual gets the same trivial
// body TupleProcessor gives it, minus the editor (no GUI dependency needed
// here). This exists purely to give an AudioProcessorValueTreeState
// something to attach to.
class TestHostProcessor : public juce::AudioProcessor
{
public:
    TestHostProcessor()
        : AudioProcessor (BusesProperties()
            .withOutput ("Out", juce::AudioChannelSet::stereo(), true)),
          apvts (*this, nullptr, "PARAMETERS", createParameterLayout())
    {
    }

    void prepareToPlay (double, int) override {}
    void releaseResources() override {}
    void processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override { buffer.clear(); }

    juce::AudioProcessorEditor* createEditor() override { return nullptr; }
    bool hasEditor() const override { return false; }

    const juce::String getName() const override { return "TestHostProcessor"; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}

    void getStateInformation (juce::MemoryBlock& destData) override
    {
        if (auto xml = apvts.copyState().createXml())
            copyXmlToBinary (*xml, destData);
    }

    void setStateInformation (const void* data, int sizeInBytes) override
    {
        if (auto xml = getXmlFromBinary (data, sizeInBytes))
            if (xml->hasTagName (apvts.state.getType()))
                apvts.replaceState (juce::ValueTree::fromXml (*xml));
    }

    juce::AudioProcessorValueTreeState apvts;
};

template <typename ParamType, typename ValueType>
void setParam (juce::AudioProcessorValueTreeState& apvts, const char* paramID, ValueType value)
{
    auto* param = dynamic_cast<ParamType*> (apvts.getParameter (paramID));
    expectTrue (param != nullptr, std::string ("parameter '") + paramID + "' exists with the expected JUCE type");
    if (param != nullptr)
        *param = value;
}

} // namespace

int main()
{
    // --- Step 3: bounds test, both ends of each of the six parameters -----
    {
        TestHostProcessor host;

        // key: int, 0..11
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kKeyParamID, tuple::plugin::kKeyMin);
        expectEqualInt (readSettings (host.apvts).key, tuple::plugin::kKeyMin, "key at min reads back correctly");
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kKeyParamID, tuple::plugin::kKeyMax);
        expectEqualInt (readSettings (host.apvts).key, tuple::plugin::kKeyMax, "key at max reads back correctly");

        // scale: int, 0..3
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kScaleParamID, tuple::plugin::kScaleMin);
        expectEqualInt (readSettings (host.apvts).scaleIndex, tuple::plugin::kScaleMin, "scale at min reads back correctly");
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kScaleParamID, tuple::plugin::kScaleMax);
        expectEqualInt (readSettings (host.apvts).scaleIndex, tuple::plugin::kScaleMax, "scale at max reads back correctly");

        // octave: int, -2..2 (signed — the min bound is the one that would
        // silently wrap to a huge value if EngineSettings.octave were ever
        // read back into a uint8_t by mistake)
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kOctaveParamID, tuple::plugin::kOctaveMin);
        expectEqualInt (readSettings (host.apvts).octave, tuple::plugin::kOctaveMin, "octave at min reads back correctly");
        setParam<juce::AudioParameterInt> (host.apvts, tuple::plugin::kOctaveParamID, tuple::plugin::kOctaveMax);
        expectEqualInt (readSettings (host.apvts).octave, tuple::plugin::kOctaveMax, "octave at max reads back correctly");

        // openness: float, 0..1
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kOpennessParamID, tuple::plugin::kOpennessMin);
        expectEqualFloat (readSettings (host.apvts).openness, tuple::plugin::kOpennessMin, "openness at min reads back correctly");
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kOpennessParamID, tuple::plugin::kOpennessMax);
        expectEqualFloat (readSettings (host.apvts).openness, tuple::plugin::kOpennessMax, "openness at max reads back correctly");

        // density: float, 0..1
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kDensityParamID, tuple::plugin::kDensityMin);
        expectEqualFloat (readSettings (host.apvts).density, tuple::plugin::kDensityMin, "density at min reads back correctly");
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kDensityParamID, tuple::plugin::kDensityMax);
        expectEqualFloat (readSettings (host.apvts).density, tuple::plugin::kDensityMax, "density at max reads back correctly");

        // register (DAW-exposed name) / centre (C++ field): float 0..127,
        // rounds into a uint8_t MIDI note — matches what
        // source/domain/Voicing.h's VoicingSettings::centre expects to
        // already receive.
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kRegisterParamID, tuple::plugin::kRegisterMin);
        expectEqualInt (readSettings (host.apvts).centre, (long long) tuple::plugin::kRegisterMin, "register at min reads back correctly into centre");
        setParam<juce::AudioParameterFloat> (host.apvts, tuple::plugin::kRegisterParamID, tuple::plugin::kRegisterMax);
        expectEqualInt (readSettings (host.apvts).centre, (long long) tuple::plugin::kRegisterMax, "register at max reads back correctly into centre");
    }

    // --- Step 4: persistence. Save state on one processor, restore it on a
    //     second, independent one, and the six values must survive the round
    //     trip. Both processors build their layout via the SAME production
    //     createParameterLayout() — if a parameter is ever removed from it,
    //     this test's read of that parameter's value fails (or the process
    //     aborts on a null getRawParameterValue() dereference inside
    //     readSettings(), which is still a hard, unmistakable failure, not a
    //     silent pass). -----------------------------------------------------
    {
        TestHostProcessor source;

        // Every value deliberately set to something OTHER than its default,
        // so a parameter that fails to round-trip (or that quietly falls
        // back to its default because it no longer exists) is caught.
        setParam<juce::AudioParameterInt>   (source.apvts, tuple::plugin::kKeyParamID,      7);
        setParam<juce::AudioParameterInt>   (source.apvts, tuple::plugin::kScaleParamID,    2);
        setParam<juce::AudioParameterInt>   (source.apvts, tuple::plugin::kOctaveParamID,  -1);
        setParam<juce::AudioParameterFloat> (source.apvts, tuple::plugin::kOpennessParamID, 0.75f);
        setParam<juce::AudioParameterFloat> (source.apvts, tuple::plugin::kDensityParamID,  0.25f);
        setParam<juce::AudioParameterFloat> (source.apvts, tuple::plugin::kRegisterParamID, 72.0f);

        juce::MemoryBlock saved;
        source.getStateInformation (saved);
        expectTrue (saved.getSize() > 0, "getStateInformation() produced a non-empty state block");

        TestHostProcessor destination;
        destination.setStateInformation (saved.getData(), (int) saved.getSize());

        auto before = readSettings (source.apvts);
        auto after  = readSettings (destination.apvts);

        expectEqualInt (after.key,        before.key,        "persisted key matches after reload");
        expectEqualInt (after.scaleIndex, before.scaleIndex, "persisted scale matches after reload");
        expectEqualInt (after.octave,     before.octave,     "persisted octave matches after reload");
        expectEqualFloat (after.openness, before.openness,   "persisted openness matches after reload");
        expectEqualFloat (after.density,  before.density,    "persisted density matches after reload");
        expectEqualInt (after.centre,     before.centre,     "persisted register (centre) matches after reload");

        // And the values are the non-default ones actually set above, not a
        // coincidental match against two freshly-defaulted processors.
        expectEqualInt (after.key, 7, "persisted key is the non-default value that was set, not the default");
    }

    if (failures == 0)
    {
        std::printf ("\nAll params tests passed.\n");
        return 0;
    }

    std::printf ("\n%d params test(s) FAILED.\n", failures);
    return 1;
}
