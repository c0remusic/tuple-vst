#pragma once

#include <cstdint>

namespace tuple::domain {

// The seven diatonic scale degrees. Task 6 (BuildGrid) produces one grid
// column per degree, plus a separate borrowed-chord region (ARCHITECTURE.md
// §5, PRD.md).
enum class Degree : uint8_t {
    I = 0,
    II,
    III,
    IV,
    V,
    VI,
    VII
};

inline constexpr uint8_t kDiatonicDegreeCount = 7;

} // namespace tuple::domain
