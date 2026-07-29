#include "ChordSpec.h"

namespace tuple::domain {

std::optional<ChordSpec> ChordSpec::make (uint8_t rootPc,
                                           std::initializer_list<ChordTone> tones)
{
    if (rootPc > 11)
        return std::nullopt;

    if (tones.size() == 0 || tones.size() > kMaxChordTones)
        return std::nullopt;

    ChordSpec spec {};
    spec.rootPc = rootPc;
    spec.count = static_cast<uint8_t> (tones.size());

    uint8_t i = 0;
    for (const auto& tone : tones)
        spec.tones[i++] = tone;

    return spec;
}

} // namespace tuple::domain
