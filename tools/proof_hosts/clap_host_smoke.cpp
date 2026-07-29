// Task 1, Step 5 proof (docs/plans/2026-07-29-phase-0-squelette.md) — "compiler,
// charger dans un DAW, capturer la preuve", CLAP side.
//
// Not part of the shipped plugin (see vst3_host_smoke.cpp for the same note).
//
// Loads the built Tuple.clap through the raw CLAP C ABI — clap_entry ->
// get_factory -> create_plugin -> init -> activate -> start_processing ->
// process -> stop_processing -> deactivate -> destroy -> deinit — the exact
// sequence every CLAP host runs. That is a materially stronger check than
// `dumpbin -exports` (which only proves the DLL exports the `clap_entry`
// symbol name): this program actually instantiates the plugin and exercises
// its lifecycle, including one real process() call.
//
// No JUCE dependency here: the platform's own dynamic loader plus the CLAP
// headers already fetched by clap-juce-extensions (build/_deps/
// clap_juce_extensions-src, no new download).
//
// PORTABILITY (2026-07-29): was Windows-only (LoadLibrary/GetProcAddress).
// Now also builds and runs on macOS/Linux via dlopen/dlsym. That port is not
// cosmetic — macOS is the ONLY platform where RealtimeSanitizer exists at all
// (`-fsanitize=realtime` is rejected outright by clang-cl for
// x86_64-pc-windows-msvc), so before this port there was no way to execute
// TupleProcessor::processBlock under the sanitizer from a host we control.
// See .github/workflows/ci.yml, Step 3.
//
// macOS bundle note: a .clap on macOS is a BUNDLE DIRECTORY, not a flat
// dylib — dlopen() on the .clap path itself fails. resolveModulePath() below
// digs out Contents/MacOS/<binary>. The ORIGINAL bundle path is still what
// gets handed to clap_entry->init(), which is what the CLAP spec asks for.
//
// What this does NOT prove: that Ableton Live's own scanner/UI accepts the
// plugin, or that its own editor opens correctly on screen; nor does it send
// real MIDI in or read notes back out (the process() call below runs one
// empty block — enough to enter processBlock, not a musical test).
// See proof/task1-build.md.

#include <clap/entry.h>
#include <clap/events.h>
#include <clap/factory/plugin-factory.h>
#include <clap/host.h>
#include <clap/plugin.h>
#include <clap/process.h>

#if defined(_WIN32)
 #include <windows.h>
#else
 #include <dirent.h>
 #include <dlfcn.h>
 #include <sys/stat.h>
#endif

#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace
{
    // --- host callbacks the plugin may call back into -----------------------
    const void* CLAP_ABI hostGetExtension (const clap_host_t*, const char*) { return nullptr; }
    void CLAP_ABI hostRequestRestart (const clap_host_t*) {}
    void CLAP_ABI hostRequestProcess (const clap_host_t*) {}
    void CLAP_ABI hostRequestCallback (const clap_host_t*) {}

    // --- event lists for process(): empty in, discard out -------------------
    uint32_t CLAP_ABI inEventsSize (const clap_input_events_t*) { return 0; }
    const clap_event_header_t* CLAP_ABI inEventsGet (const clap_input_events_t*, uint32_t) { return nullptr; }
    bool CLAP_ABI outEventsTryPush (const clap_output_events_t*, const clap_event_header_t*) { return true; }

    // --- the one piece that differs per platform ----------------------------
#if defined(_WIN32)
    using ModuleHandle = HMODULE;

    ModuleHandle openModule (const std::string& path) { return LoadLibraryA (path.c_str()); }
    void* moduleSymbol (ModuleHandle m, const char* name) { return reinterpret_cast<void*> (GetProcAddress (m, name)); }
    void closeModule (ModuleHandle m) { FreeLibrary (m); }

    std::string openError (const std::string& path)
    {
        return "LoadLibrary(" + path + ") failed, error " + std::to_string (GetLastError());
    }

    // Windows .clap files are flat DLLs; nothing to dig into.
    bool resolveModulePath (const std::string& bundlePath, std::string& out, std::string& error)
    {
        (void) error;
        out = bundlePath;
        return true;
    }
#else
    using ModuleHandle = void*;

    ModuleHandle openModule (const std::string& path) { return dlopen (path.c_str(), RTLD_NOW | RTLD_LOCAL); }
    void* moduleSymbol (ModuleHandle m, const char* name) { return dlsym (m, name); }
    void closeModule (ModuleHandle m) { dlclose (m); }

    std::string openError (const std::string& path)
    {
        const char* e = dlerror();
        return "dlopen(" + path + ") failed: " + (e != nullptr ? e : "(dlerror returned null)");
    }

    // A macOS .clap is a bundle directory. Anything that is NOT a directory is
    // taken as a plain shared object (Linux .clap, or a bare .dylib) and used
    // as-is. Deliberately no <filesystem>: JUCE's CMAKE_OSX_DEPLOYMENT_TARGET
    // can sit below the 10.15 that libc++'s std::filesystem requires, and this
    // tool must build wherever the plugin does.
    bool resolveModulePath (const std::string& bundlePath, std::string& out, std::string& error)
    {
        struct stat st {};
        if (stat (bundlePath.c_str(), &st) != 0)
        {
            error = "path does not exist: " + bundlePath;
            return false;
        }

        if (! S_ISDIR (st.st_mode))
        {
            out = bundlePath;
            return true;
        }

        const std::string macosDir = bundlePath + "/Contents/MacOS";
        DIR* dir = opendir (macosDir.c_str());
        if (dir == nullptr)
        {
            error = bundlePath + " is a directory but has no Contents/MacOS — not a CLAP bundle";
            return false;
        }

        // Collect ALL candidates rather than taking the first: two executables
        // in Contents/MacOS means the layout is not what this tool assumes, and
        // guessing which one is the plugin would be exactly the kind of silent
        // fallback that turns into a mystery later.
        std::vector<std::string> candidates;
        while (const dirent* e = readdir (dir))
        {
            const std::string name = e->d_name;
            if (name == "." || name == "..")
                continue;

            const std::string candidate = macosDir + "/" + name;
            struct stat cs {};
            if (stat (candidate.c_str(), &cs) == 0 && S_ISREG (cs.st_mode))
                candidates.push_back (candidate);
        }
        closedir (dir);

        if (candidates.size() != 1)
        {
            error = "expected exactly one binary in " + macosDir + ", found "
                  + std::to_string (candidates.size());
            return false;
        }

        out = candidates.front();
        return true;
    }
#endif
}

int main (int argc, char* argv[])
{
    if (argc < 2)
    {
        std::fprintf (stderr, "usage: clap_host_smoke <path-to-.clap>\n");
        return 2;
    }

    // bundlePath is what the CLAP spec says to pass to clap_entry->init();
    // modulePath is what the platform's loader needs. On Windows they are the
    // same string, on macOS they are not.
    const std::string bundlePath = argv[1];
    std::string modulePath;
    std::string resolveError;

    if (! resolveModulePath (bundlePath, modulePath, resolveError))
    {
        std::fprintf (stderr, "FAIL: %s\n", resolveError.c_str());
        return 1;
    }

    if (modulePath != bundlePath)
        std::printf ("OK: resolved bundle %s -> %s\n", bundlePath.c_str(), modulePath.c_str());

    ModuleHandle module = openModule (modulePath);
    if (module == nullptr)
    {
        std::fprintf (stderr, "FAIL: %s\n", openError (modulePath).c_str());
        return 1;
    }

    const auto* entry = reinterpret_cast<const clap_plugin_entry_t*> (moduleSymbol (module, "clap_entry"));
    if (entry == nullptr)
    {
        std::fprintf (stderr, "FAIL: clap_entry symbol not found\n");
        closeModule (module);
        return 1;
    }

    if (! entry->init (bundlePath.c_str()))
    {
        std::fprintf (stderr, "FAIL: clap_entry->init() returned false\n");
        closeModule (module);
        return 1;
    }

    const auto* factory = reinterpret_cast<const clap_plugin_factory_t*> (entry->get_factory (CLAP_PLUGIN_FACTORY_ID));
    if (factory == nullptr)
    {
        std::fprintf (stderr, "FAIL: get_factory(CLAP_PLUGIN_FACTORY_ID) returned null\n");
        entry->deinit();
        closeModule (module);
        return 1;
    }

    const uint32_t count = factory->get_plugin_count (factory);
    if (count == 0)
    {
        std::fprintf (stderr, "FAIL: factory reports 0 plugins\n");
        entry->deinit();
        closeModule (module);
        return 1;
    }

    const clap_plugin_descriptor_t* desc = factory->get_plugin_descriptor (factory, 0);
    if (desc == nullptr)
    {
        std::fprintf (stderr, "FAIL: get_plugin_descriptor(0) returned null\n");
        entry->deinit();
        closeModule (module);
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
        closeModule (module);
        return 1;
    }

    if (! plugin->init (plugin))
    {
        std::fprintf (stderr, "FAIL: plugin->init() returned false\n");
        plugin->destroy (plugin);
        entry->deinit();
        closeModule (module);
        return 1;
    }

    constexpr uint32_t kFrames = 512;

    if (! plugin->activate (plugin, 44100.0, 32, kFrames))
    {
        std::fprintf (stderr, "FAIL: plugin->activate() returned false\n");
        plugin->destroy (plugin);
        entry->deinit();
        closeModule (module);
        return 1;
    }

    if (! plugin->start_processing (plugin))
    {
        std::fprintf (stderr, "FAIL: plugin->start_processing() returned false\n");
        plugin->deactivate (plugin);
        plugin->destroy (plugin);
        entry->deinit();
        closeModule (module);
        return 1;
    }

    // One real process() call. This is the whole reason the port above exists:
    // it is the CLAP-side path that ends up inside TupleProcessor::processBlock,
    // which carries TUPLE_NONBLOCKING — so under -fsanitize=realtime this call,
    // and only a call like it, puts Tuple's own audio code in real-time context.
    // Tuple declares a stereo output bus (fake, see PluginProcessor.cpp) and no
    // audio input.
    float leftData[kFrames] {};
    float rightData[kFrames] {};
    float* channels[2] = { leftData, rightData };

    clap_audio_buffer_t audioOut {};
    audioOut.data32 = channels;
    audioOut.data64 = nullptr;
    audioOut.channel_count = 2;
    audioOut.latency = 0;
    audioOut.constant_mask = 0;

    clap_input_events_t inEvents {};
    inEvents.ctx = nullptr;
    inEvents.size = inEventsSize;
    inEvents.get = inEventsGet;

    clap_output_events_t outEvents {};
    outEvents.ctx = nullptr;
    outEvents.try_push = outEventsTryPush;

    clap_process_t process {};
    process.steady_time = 0;
    process.frames_count = kFrames;
    process.transport = nullptr;
    process.audio_inputs = nullptr;
    process.audio_inputs_count = 0;
    process.audio_outputs = &audioOut;
    process.audio_outputs_count = 1;
    process.in_events = &inEvents;
    process.out_events = &outEvents;

    const clap_process_status status = plugin->process (plugin, &process);
    if (status == CLAP_PROCESS_ERROR)
    {
        std::fprintf (stderr, "FAIL: plugin->process() returned CLAP_PROCESS_ERROR\n");
        plugin->stop_processing (plugin);
        plugin->deactivate (plugin);
        plugin->destroy (plugin);
        entry->deinit();
        closeModule (module);
        return 1;
    }

    std::printf ("OK: process() ran one %u-frame block, status=%d\n", kFrames, (int) status);

    plugin->stop_processing (plugin);
    plugin->deactivate (plugin);
    plugin->destroy (plugin);
    entry->deinit();
    closeModule (module);

    std::printf ("OK: init -> activate -> start_processing -> process -> stop_processing -> deactivate -> destroy -> deinit, no crash\n");
    return 0;
}
