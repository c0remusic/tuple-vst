// Fast domain test binary (ARCHITECTURE.md §1): no JUCE, starts in about a
// second. No third-party test framework is used — a self-contained runner
// keeps the licence surface (THIRD-PARTY-LICENSES.md) unchanged for Phase 0.
//
// Task 2, Step 1: written and run BEFORE ChordSpec::make has a definition.
// At this point source/domain/ChordSpec.cpp does not exist, so this binary
// is expected to fail to LINK (undefined reference to ChordSpec::make) —
// that is the RED state.

#include "../source/domain/ChordSpec.h"

#include <cstdio>

using tuple::domain::ChordSpec;
using tuple::domain::ChordTone;
using tuple::domain::Role;

namespace {

int failures = 0;

void expectTrue (bool condition, const char* description)
{
    if (condition)
    {
        std::printf ("[PASS] %s\n", description);
    }
    else
    {
        std::printf ("[FAIL] %s\n", description);
        ++failures;
    }
}

} // namespace

int main()
{
    // --- make() rejects rootPc > 11 ---------------------------------------
    expectTrue (! ChordSpec::make (12, { { 0, Role::Root } }).has_value(),
                "make rejects rootPc == 12");
    expectTrue (! ChordSpec::make (255, { { 0, Role::Root } }).has_value(),
                "make rejects rootPc == 255");
    expectTrue (ChordSpec::make (11, { { 0, Role::Root } }).has_value(),
                "make accepts rootPc == 11 (highest valid pitch class)");
    expectTrue (ChordSpec::make (0, { { 0, Role::Root } }).has_value(),
                "make accepts rootPc == 0 (lowest valid pitch class)");

    // --- make() rejects 0 or more than 6 tones ----------------------------
    {
        auto empty = ChordSpec::make (0, {});
        expectTrue (! empty.has_value(), "make rejects an empty tone list");
    }
    {
        // Seven tones: one more than kMaxChordTones (6).
        auto sevenTones = ChordSpec::make (0, {
            { 0, Role::Root }, { 2, Role::Ninth }, { 4, Role::Third },
            { 5, Role::Eleventh }, { 7, Role::Fifth }, { 9, Role::Thirteenth },
            { 11, Role::Seventh }
        });
        expectTrue (! sevenTones.has_value(), "make rejects 7 tones (kMaxChordTones == 6)");
    }
    {
        // Exactly 6 tones: the boundary, must be accepted.
        auto sixTones = ChordSpec::make (0, {
            { 0, Role::Root }, { 2, Role::Ninth }, { 4, Role::Third },
            { 5, Role::Eleventh }, { 7, Role::Fifth }, { 9, Role::Thirteenth }
        });
        expectTrue (sixTones.has_value(), "make accepts exactly 6 tones (the upper bound)");
    }

    // --- a valid chord is accepted and role order is preserved -----------
    {
        // Cmaj7: root, third, fifth, seventh, in that order.
        auto cmaj7 = ChordSpec::make (0, {
            { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth }, { 11, Role::Seventh }
        });
        expectTrue (cmaj7.has_value(), "make accepts a valid Cmaj7 spec");
        if (cmaj7)
        {
            expectTrue (cmaj7->rootPc == 0, "Cmaj7 rootPc is 0");
            expectTrue (cmaj7->count == 4, "Cmaj7 count is 4");
            expectTrue (cmaj7->tones[0].role == Role::Root, "tone[0] role preserved as Root");
            expectTrue (cmaj7->tones[1].role == Role::Third, "tone[1] role preserved as Third");
            expectTrue (cmaj7->tones[2].role == Role::Fifth, "tone[2] role preserved as Fifth");
            expectTrue (cmaj7->tones[3].role == Role::Seventh, "tone[3] role preserved as Seventh");
            expectTrue (cmaj7->tones[0].semitones == 0, "tone[0] semitones preserved as 0");
            expectTrue (cmaj7->tones[3].semitones == 11, "tone[3] semitones preserved as 11");
        }
    }

    if (failures == 0)
    {
        std::printf ("\nAll domain tests passed.\n");
        return 0;
    }

    std::printf ("\n%d domain test(s) FAILED.\n", failures);
    return 1;
}
