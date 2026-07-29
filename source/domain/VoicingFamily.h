#pragma once

#include <cstdint>

namespace tuple::domain {

// The six structurally distinct ways of redistributing the same chord tones
// (ARCHITECTURE.md §5 bis). Not a genre catalogue: the Max for Live device's
// preset names (house, trance, funk, deeptech...) do not carry over — see
// the Phase 0 plan's "Tranché" note under ARCHITECTURE.md §9.
enum class VoicingFamily : uint8_t {
    Close = 0,
    Open,
    Drop,
    Rootless,
    Quartal,
    TwoHand
};

inline constexpr uint8_t kVoicingFamilyCount = 6;

} // namespace tuple::domain
