#pragma once

#include <cstdint>

namespace tuple::domain {

// A pitch class, 0 = C .. 11 = B. The domain stores keys as plain uint8_t
// everywhere (see ChordSpec::rootPc, HarmonicContext::key) — this enum exists
// only to give the twelve values names at call sites; it carries no
// behaviour of its own.
enum class Key : uint8_t {
    C = 0,
    CSharp,
    D,
    DSharp,
    E,
    F,
    FSharp,
    G,
    GSharp,
    A,
    ASharp,
    B
};

constexpr bool isValidKey (uint8_t pitchClass) noexcept
{
    return pitchClass <= 11;
}

} // namespace tuple::domain
