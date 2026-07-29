// Task 1, Step 5 proof (docs/plans/2026-07-29-phase-0-squelette.md) — "compiler,
// charger dans un DAW, capturer la preuve".
//
// This is NOT part of the shipped plugin: it lives outside source/plugin,
// is not part of the domain/app/plugin architecture, and is never built into
// the .vst3/.clap. It exists solely to produce verifiable proof for Step 5.
//
// It loads the built Tuple.vst3 through JUCE's own VST3 *hosting* classes
// (juce::VST3PluginFormat / AudioPluginFormat) — the exact same code path
// every JUCE-based host (e.g. Tracktion Waveform) uses to load a VST3 plugin.
// That is a materially stronger check than `dumpbin -exports` (which only
// proves the DLL exports the right symbol names): this program actually
// invokes the plugin's IPluginFactory, instantiates the processor, runs
// prepareToPlay/processBlock/releaseResources, and destroys it.
//
// What this does NOT prove: that Ableton Live's own scanner/UI accepts the
// plugin, or that its own editor opens correctly on screen. See
// proof/task1-build.md for why a live GUI DAW session was not captured on
// this machine, and what would close that remaining gap.
//
// JUCE_PLUGINHOST_VST3 is defined only for THIS target (see CMakeLists.txt).
// The shipped TupleVST target never links the hosting side of JUCE.
//
// PORTABILITY (2026-07-29): this file never used a Win32 API — JUCE's hosting
// classes are cross-platform — but CMakeLists.txt used to gate BOTH proof
// hosts behind `AND WIN32` because its sibling, clap_host_smoke.cpp, did. That
// gate is gone now that the sibling is ported, so this runs on macOS too,
// which matters for one specific reason: macOS is the only platform where
// RealtimeSanitizer exists, and when this program is itself built with
// -fsanitize=realtime it becomes the host that can legitimately execute an
// RTSan-instrumented plugin. A pre-built host cannot: the sanitizer runtime
// would arrive via the plugin's own dlopen, too late to install its
// interceptors, and abort ("Interceptors are not working", observed on CI run
// 30437655033 with pluginval). See .github/workflows/ci.yml, Step 3.

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_events/juce_events.h>

#include <cstdio>
#include <memory>

int main (int argc, char* argv[])
{
    if (argc < 2)
    {
        std::fprintf (stderr, "usage: vst3_host_smoke <path-to-.vst3>\n");
        return 2;
    }

    // Initialises JUCE's message loop machinery. No window is ever shown;
    // some JUCE plugin-hosting internals still expect it to exist.
    juce::ScopedJuceInitialiser_GUI juceInit;

    juce::VST3PluginFormat format;
    juce::OwnedArray<juce::PluginDescription> found;
    format.findAllTypesForFile (found, juce::String (argv[1]));

    if (found.isEmpty())
    {
        std::fprintf (stderr, "FAIL: findAllTypesForFile found no plugin types in %s\n", argv[1]);
        return 1;
    }

    juce::String errorMessage;
    std::unique_ptr<juce::AudioPluginInstance> instance (
        format.createInstanceFromDescription (*found.getFirst(), 44100.0, 512, errorMessage));

    if (instance == nullptr)
    {
        std::fprintf (stderr, "FAIL: createInstanceFromDescription: %s\n", errorMessage.toRawUTF8());
        return 1;
    }

    std::printf ("OK: instantiated \"%s\" via VST3PluginFormat, %d in / %d out, %d parameters\n",
                 instance->getName().toRawUTF8(),
                 instance->getTotalNumInputChannels(),
                 instance->getTotalNumOutputChannels(),
                 instance->getParameters().size());

    instance->prepareToPlay (44100.0, 512);

    juce::AudioBuffer<float> audio (juce::jmax (1, instance->getTotalNumOutputChannels()), 512);
    audio.clear();
    juce::MidiBuffer midi;
    instance->processBlock (audio, midi);

    instance->releaseResources();
    instance.reset();

    std::printf ("OK: prepareToPlay -> processBlock -> releaseResources -> destroyed, no crash\n");
    return 0;
}
