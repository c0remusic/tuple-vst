// Task 1, Step 5 proof (docs/plans/2026-07-29-phase-0-squelette.md) — "compiler,
// charger dans un DAW, capturer la preuve", CLAP side.
//
// Not part of the shipped plugin (see vst3_host_smoke.cpp for the same note).
//
// Loads the built Tuple.clap through the raw CLAP C ABI — clap_entry ->
// get_factory -> create_plugin -> init -> activate -> start_processing ->
// stop_processing -> deactivate -> destroy -> deinit — the exact sequence
// every CLAP host runs. That is a materially stronger check than
// `dumpbin -exports` (which only proves the DLL exports the `clap_entry`
// symbol name): this program actually instantiates the plugin and exercises
// its lifecycle.
//
// No JUCE dependency here: plain Win32 LoadLibrary + the CLAP headers already
// fetched by clap-juce-extensions (build/_deps/clap_juce_extensions-src,
// no new download). Windows-only for now, like the rest of this proof tool —
// see CMakeLists.txt.
//
// What this does NOT prove: that Ableton Live's own scanner/UI accepts the
// plugin, or that its own editor opens correctly on screen; nor does it send
// real audio/MIDI through process() (that is Task 5/7's job, not Step 5's).
// See proof/task1-build.md.

#include <clap/entry.h>
#include <clap/factory/plugin-factory.h>
#include <clap/host.h>
#include <clap/plugin.h>

#include <windows.h>

#include <cstdio>
#include <string>

namespace
{
    const void* CLAP_ABI hostGetExtension (const clap_host_t*, const char*) { return nullptr; }
    void CLAP_ABI hostRequestRestart (const clap_host_t*) {}
    void CLAP_ABI hostRequestProcess (const clap_host_t*) {}
    void CLAP_ABI hostRequestCallback (const clap_host_t*) {}
}

int main (int argc, char* argv[])
{
    if (argc < 2)
    {
        std::fprintf (stderr, "usage: clap_host_smoke <path-to-.clap>\n");
        return 2;
    }

    const std::string path = argv[1];
    HMODULE module = LoadLibraryA (path.c_str());
    if (module == nullptr)
    {
        std::fprintf (stderr, "FAIL: LoadLibrary(%s) failed, error %lu\n", path.c_str(), GetLastError());
        return 1;
    }

    const auto* entry = reinterpret_cast<const clap_plugin_entry_t*> (GetProcAddress (module, "clap_entry"));
    if (entry == nullptr)
    {
        std::fprintf (stderr, "FAIL: clap_entry symbol not found\n");
        FreeLibrary (module);
        return 1;
    }

    if (! entry->init (path.c_str()))
    {
        std::fprintf (stderr, "FAIL: clap_entry->init() returned false\n");
        FreeLibrary (module);
        return 1;
    }

    const auto* factory = reinterpret_cast<const clap_plugin_factory_t*> (entry->get_factory (CLAP_PLUGIN_FACTORY_ID));
    if (factory == nullptr)
    {
        std::fprintf (stderr, "FAIL: get_factory(CLAP_PLUGIN_FACTORY_ID) returned null\n");
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    const uint32_t count = factory->get_plugin_count (factory);
    if (count == 0)
    {
        std::fprintf (stderr, "FAIL: factory reports 0 plugins\n");
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    const clap_plugin_descriptor_t* desc = factory->get_plugin_descriptor (factory, 0);
    if (desc == nullptr)
    {
        std::fprintf (stderr, "FAIL: get_plugin_descriptor(0) returned null\n");
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    std::printf ("OK: factory describes \"%s\" (id=%s)\n", desc->name, desc->id);

    clap_host_t host {};
    host.clap_version = CLAP_VERSION;
    host.host_data = nullptr;
    host.name = "TupleVST proof host (smoke test, not a DAW)";
    host.vendor = "Tuple";
    host.url = "";
    host.version = "0.0.0";
    host.get_extension = hostGetExtension;
    host.request_restart = hostRequestRestart;
    host.request_process = hostRequestProcess;
    host.request_callback = hostRequestCallback;

    const clap_plugin_t* plugin = factory->create_plugin (factory, &host, desc->id);
    if (plugin == nullptr)
    {
        std::fprintf (stderr, "FAIL: create_plugin returned null\n");
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    if (! plugin->init (plugin))
    {
        std::fprintf (stderr, "FAIL: plugin->init() returned false\n");
        plugin->destroy (plugin);
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    if (! plugin->activate (plugin, 44100.0, 32, 512))
    {
        std::fprintf (stderr, "FAIL: plugin->activate() returned false\n");
        plugin->destroy (plugin);
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    if (! plugin->start_processing (plugin))
    {
        std::fprintf (stderr, "FAIL: plugin->start_processing() returned false\n");
        plugin->deactivate (plugin);
        plugin->destroy (plugin);
        entry->deinit();
        FreeLibrary (module);
        return 1;
    }

    plugin->stop_processing (plugin);
    plugin->deactivate (plugin);
    plugin->destroy (plugin);
    entry->deinit();
    FreeLibrary (module);

    std::printf ("OK: init -> activate -> start_processing -> stop_processing -> deactivate -> destroy -> deinit, no crash\n");
    return 0;
}
