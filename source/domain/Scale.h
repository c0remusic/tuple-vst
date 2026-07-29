#pragma once

#include <array>
#include <cstdint>

#include "Degree.h"

namespace tuple::domain {

// A scale names seven semitone distances from its tonic, one per diatonic
// degree. This is groundwork for Task 6's BuildGrid, not a definitive list —
// unlike the six plugin parameters or the plugin identifiers, the scale
// catalogue is not frozen by ARCHITECTURE.md.
enum class Scale : uint8_t {
    Major = 0,
    NaturalMinor,
    HarmonicMinor,
    MelodicMinor
};

inline constexpr uint8_t kScaleCount = 4;

using ScaleIntervals = std::array<uint8_t, kDiatonicDegreeCount>;

constexpr ScaleIntervals intervalsFor (Scale scale) noexcept
{
    switch (scale)
    {
        case Scale::Major:         return { 0, 2, 4, 5, 7, 9, 11 };
        case Scale::NaturalMinor:  return { 0, 2, 3, 5, 7, 8, 10 };
        case Scale::HarmonicMinor: return { 0, 2, 3, 5, 7, 8, 11 };
        case Scale::MelodicMinor:  return { 0, 2, 3, 5, 7, 9, 11 };
    }
    return { 0, 2, 4, 5, 7, 9, 11 }; // unreachable; keeps -Wreturn-type quiet
}

constexpr bool isValidScaleIndex (uint8_t scaleIndex) noexcept
{
    return scaleIndex < kScaleCount;
}

} // namespace tuple::domain
