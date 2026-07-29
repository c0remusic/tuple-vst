#pragma once

#include <cstdint>

namespace tuple::plugin {

// Stable, host-facing parameter identifiers (ARCHITECTURE.md §5 bis, Task 4).
// These six strings are DEFINITIVE: renaming any one breaks every project a
// user has already saved with this plugin — do not "clean them up" later.
//
// `register` is a reserved word in C++. The identifier exposed to the DAW is
// still the bare string "register" (kRegisterParamID below); the C++ field
// that holds its value is EngineSettings::centre. This split is deliberate
// (Global Constraints, "register est un mot reserve") — do not rename one to
// match the other.
inline constexpr const char* kKeyParamID      = "key";
inline constexpr const char* kScaleParamID    = "scale";
inline constexpr const char* kOctaveParamID   = "octave";
inline constexpr const char* kOpennessParamID = "openness";
inline constexpr const char* kDensityParamID  = "density";
inline constexpr const char* kRegisterParamID = "register";

// Ranges and defaults: the single source of truth for both
// ParameterAdapter::createParameterLayout() (which declares the six APVTS
// parameters) and tests/params_tests.cpp (which exercises their bounds) —
// kept here so the two cannot silently drift apart.
inline constexpr int kKeyMin = 0;
inline constexpr int kKeyMax = 11;
inline constexpr int kKeyDefault = 0;

// ARCHITECTURE.md does not fix a numeric scale count in the parameter table;
// this mirrors source/domain/Scale.h's kScaleCount (4: Major, NaturalMinor,
// HarmonicMinor, MelodicMinor) without including that header here, so the
// plugin layer's parameter declaration does not depend on the domain layer's
// enum ordering to compile.
inline constexpr int kScaleMin = 0;
inline constexpr int kScaleMax = 3;
inline constexpr int kScaleDefault = 0;

// "Entier borne" (ARCHITECTURE.md §5 bis) without a numeric bound fixed
// elsewhere in the plan/architecture; -2..+2 is a Phase 0 implementation
// choice (five octaves of base-register shift), not a value pinned by a
// spec — revisit if a later task documents a different range.
inline constexpr int kOctaveMin = -2;
inline constexpr int kOctaveMax = 2;
inline constexpr int kOctaveDefault = 0;

inline constexpr float kOpennessMin = 0.0f;
inline constexpr float kOpennessMax = 1.0f;
inline constexpr float kOpennessDefault = 0.5f;

inline constexpr float kDensityMin = 0.0f;
inline constexpr float kDensityMax = 1.0f;
inline constexpr float kDensityDefault = 0.5f;

// 0..127 is a MIDI note number. This matches, on purpose, what
// source/domain/Voicing.h's VoicingSettings::centre already documents as its
// contract: "centre is expected to already be a valid MIDI note (0..127)".
// ParameterAdapter::readSettings() rounds this float into that uint8_t.
inline constexpr float kRegisterMin = 0.0f;
inline constexpr float kRegisterMax = 127.0f;
inline constexpr float kRegisterDefault = 60.0f; // middle C

// The plugin-side snapshot of the six parameters (ARCHITECTURE.md §5 bis).
// Deliberately no JUCE type: ParameterAdapter::readSettings() is the ONLY
// place a juce::AudioProcessorValueTreeState is translated into this struct
// (Task 4, Global Constraints); everything downstream only ever sees this
// plain, fixed-size, stack-friendly value.
struct EngineSettings
{
    uint8_t key;
    uint8_t scaleIndex;
    int8_t  octave;
    float   openness;
    float   density;
    uint8_t centre;
};

} // namespace tuple::plugin
