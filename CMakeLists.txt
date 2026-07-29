cmake_minimum_required(VERSION 3.22)

project(TupleVST VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# --- RealtimeSanitizer switch (ARCHITECTURE.md §6) --------------------------
# OFF by default. Task 7 turns it on in CI. Only Clang >= 20 understands the
# flag; on any other compiler we warn and ignore rather than fail the build.
option(TUPLE_RTSAN "Build with RealtimeSanitizer (-fsanitize=realtime)" OFF)

# --- JUCE, pinned tag, never a floating branch ------------------------------
include(FetchContent)

FetchContent_Declare(JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 9.0.0
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(JUCE)

# --- CLAP support via clap-juce-extensions ----------------------------------
# MIT license (verified 2026-07-29 via GitHub's license API on the upstream
# repo). Pinned to a commit SHA rather than the latest tag: the newest tagged
# release (0.26.0) predates JUCE 9 by three years and does not build against
# it. JUCE 9 support landed on `main` in commit 26bab6be ("JUCE 9 support
# (#178)") and has not been tagged upstream yet. The SHA below is that same
# commit (HEAD of `main` as of 2026-07-29) — an immutable commit reference,
# not a moving branch name, so it still satisfies "no floating branch".
set(CLAP_JUCE_EXTENSIONS_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_Declare(clap_juce_extensions
    GIT_REPOSITORY https://github.com/free-audio/clap-juce-extensions.git
    GIT_TAG 54b3c3268ab6721a7afeef813c9e1ce43a3d0fcd
    GIT_SUBMODULES_RECURSE TRUE
)
FetchContent_MakeAvailable(clap_juce_extensions)

# --- The plugin target -------------------------------------------------------
# Identifiers are definitive at life (Global Constraints). FORMATS is VST3
# only here: AAX and ASIO are never requested, so neither SDK is ever fetched
# or linked. CLAP is added below through clap_juce_extensions_plugin().
juce_add_plugin(TupleVST
    COMPANY_NAME                "Tuple"
    PLUGIN_MANUFACTURER_CODE    Tupl
    PLUGIN_CODE                 Chrd
    PRODUCT_NAME                "Tuple"
    BUNDLE_ID                   "live.tuple.chords"
    FORMATS                     VST3
    IS_SYNTH                    TRUE
    NEEDS_MIDI_INPUT            TRUE
    NEEDS_MIDI_OUTPUT           TRUE
    IS_MIDI_EFFECT              FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
    # OFF: the default install path is C:/Program Files/Common Files/VST3,
    # which needs admin rights this dev machine doesn't have non-elevated.
    # Point your DAW's VST3 scan path at the build output instead (see
    # proof/ for the exact artefact path), or copy it there yourself.
    COPY_PLUGIN_AFTER_BUILD     FALSE
    VST3_CATEGORIES             Instrument
)

target_sources(TupleVST PRIVATE
    source/plugin/PluginProcessor.cpp
    source/plugin/PluginEditor.cpp
)

target_include_directories(TupleVST PRIVATE source/plugin)

target_compile_features(TupleVST PRIVATE cxx_std_17)

# Never AAX, never ASIO (ARCHITECTURE.md §4); WEB_BROWSER pulls in WebKitGTK
# on Linux and isn't used; MP3 support ships with an explicit "not guaranteed
# free of IP infringement" warning from JUCE itself.
target_compile_definitions(TupleVST PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_MP3AUDIOFORMAT=0
    # Never released a VST2 build of this plugin, and never will (no VST2 SDK
    # is fetched or linked here) — JUCE's own guidance for this exact case.
    JUCE_VST3_CAN_REPLACE_VST2=0
)

target_link_libraries(TupleVST PRIVATE
    juce::juce_audio_utils
    juce::juce_audio_processors
    PUBLIC
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

if(TUPLE_RTSAN)
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
        target_compile_options(TupleVST PRIVATE -fsanitize=realtime)
        target_link_options(TupleVST PRIVATE -fsanitize=realtime)
    else()
        message(WARNING "TUPLE_RTSAN is ON but compiler '${CMAKE_CXX_COMPILER_ID}' "
                         "does not support -fsanitize=realtime (Clang >= 20 required). Ignoring.")
    endif()
endif()

clap_juce_extensions_plugin(TARGET TupleVST
    CLAP_ID "live.tuple.chords"
    CLAP_FEATURES instrument
)
