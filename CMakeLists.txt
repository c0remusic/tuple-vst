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
# Licence: JUCE is dual-licensed by Raw Material Software — commercial, or
# AGPLv3 (verified on-disk: every vendored JUCE header carries both terms
# verbatim, e.g. modules/juce_audio_processors_headless/format/
# juce_PluginFormatDefs.h after FetchContent runs; canonical text at
# https://juce.com/legal/juce-9-licence/). AGPLv3 is copyleft, so Global
# Constraints ("aucune dependance copyleft") rules it out — this project is
# under the commercial licence, Starter tier, whose criterion (Raw Material
# Software EULA) is "revenue or funding received by the entity and its
# affiliates, from all sources, over the trailing 12 months <= $20,000". See
# THIRD-PARTY-LICENSES.md for the full record and the re-verification trigger,
# and ARCHITECTURE.md Section 3 for the tier table and pitfalls. Holding the
# actual Starter seat (an account with Raw Material Software) is a business
# action taken outside this repository, not a file this CMakeLists.txt can
# produce — this comment documents the applicable terms and where to recheck
# them, not a substitute for that registration.
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
# (#178)", 2026-07-21). The SHA below, 54b3c326, is NOT that same commit: it
# is the one commit directly after it ("Fix null termination of CLAP metadata
# strings (#179)"), confirmed via the GitHub compare API on 2026-07-29
# (26bab6be...54b3c326 -> ahead_by: 1, one commit). It still satisfies "pinned
# commit, not a floating branch" — 26bab6be (the JUCE 9 support commit) is
# included as its direct ancestor either way.
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
    source/plugin/ParameterAdapter.cpp
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

# --- Proof-only host smoke tests (Task 1, Step 5) ---------------------------
# tools/proof_hosts/ is NOT the plugin: it is outside the domain/app/plugin
# architecture, never linked into the .vst3/.clap, and exists solely to prove
# "loads in a real host, doesn't crash" with something stronger than
# `dumpbin -exports`. See proof/task1-build.md and the .cpp files themselves.
# Windows-only for now (both smoke tests currently rely on Win32 APIs); a
# macOS pass needs the LoadLibrary/GetProcAddress calls in
# clap_host_smoke.cpp swapped for dlopen/dlsym when a Mac is available.
option(TUPLE_BUILD_PROOF_HOSTS "Build the Task-1-Step-5 host-loading smoke tests" ON)

# --- Domain test binary (Task 2) --------------------------------------------
# No JUCE dependency, no link against TupleVST: this is the fast loop
# ARCHITECTURE.md §1 describes ("demarre en une seconde, sans hote audio").
# Only source/domain/*.cpp is compiled in, so it also proves the domain layer
# builds standalone (Task 2 Step 5).
add_executable(DomainTests
    tests/domain_tests.cpp
    source/domain/ChordSpec.cpp
)
target_include_directories(DomainTests PRIVATE source/domain)
target_compile_features(DomainTests PRIVATE cxx_std_17)

# --- Voicing test binary (Task 3) -------------------------------------------
# Same fast-loop rationale as DomainTests: no JUCE, standalone. The fixture
# path is passed as an absolute define so the binary finds
# fixtures/voicing_basic.txt regardless of the working directory it is run
# from (build output dir, CTest, CI runner...).
add_executable(VoicingTests
    tests/voicing_tests.cpp
    source/domain/ChordSpec.cpp
    source/domain/Voicing.cpp
)
target_include_directories(VoicingTests PRIVATE source/domain)
target_compile_features(VoicingTests PRIVATE cxx_std_17)
target_compile_definitions(VoicingTests PRIVATE
    TUPLE_FIXTURES_DIR="${CMAKE_SOURCE_DIR}/fixtures")

# --- Params test binary (Task 4) --------------------------------------------
# Unlike DomainTests/VoicingTests this one DOES need JUCE (ParameterAdapter is
# the seam where a JUCE type touches settings), but it stays as shallow a
# JUCE dependency as the task allows: juce_audio_processors + juce_events,
# no juce_gui_basics (see tests/params_tests.cpp's TestHostProcessor).
add_executable(ParamsTests
    tests/params_tests.cpp
    source/plugin/ParameterAdapter.cpp
)
target_include_directories(ParamsTests PRIVATE source/plugin)
target_compile_features(ParamsTests PRIVATE cxx_std_17)
target_compile_definitions(ParamsTests PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_MP3AUDIOFORMAT=0
)
target_link_libraries(ParamsTests PRIVATE
    juce::juce_audio_processors
    juce::juce_events
    juce::juce_recommended_config_flags
    juce::juce_recommended_warning_flags
)

if(TUPLE_BUILD_PROOF_HOSTS AND WIN32)
    juce_add_console_app(TupleVST3HostSmoke
        PRODUCT_NAME "TupleVST3HostSmoke"
    )
    target_sources(TupleVST3HostSmoke PRIVATE tools/proof_hosts/vst3_host_smoke.cpp)
    target_compile_definitions(TupleVST3HostSmoke PRIVATE
        JUCE_PLUGINHOST_VST3=1
        JUCE_WEB_BROWSER=0
        JUCE_USE_MP3AUDIOFORMAT=0
    )
    target_link_libraries(TupleVST3HostSmoke PRIVATE
        juce::juce_audio_processors
        juce::juce_audio_basics
        juce::juce_events
        juce::juce_recommended_config_flags
        juce::juce_recommended_warning_flags
    )

    add_executable(TupleClapHostSmoke tools/proof_hosts/clap_host_smoke.cpp)
    target_include_directories(TupleClapHostSmoke PRIVATE
        ${clap_juce_extensions_SOURCE_DIR}/clap-libs/clap/include
    )
    target_compile_features(TupleClapHostSmoke PRIVATE cxx_std_17)
endif()
