// Task 6 grid tests (docs/plans/2026-07-29-phase-0-squelette.md). No
// third-party framework, same self-contained runner style as
// tests/domain_tests.cpp / tests/voicing_tests.cpp / tests/noteoff_tests.cpp.
//
// Task 6, Step 1: written and run BEFORE source/app/BuildGrid.cpp defines
// buildGrid(). At this point CMakeLists' GridTests target lists a
// BuildGrid.cpp that declares but does not define buildGrid(), so this
// binary is expected to fail to LINK (undefined reference to
// tuple::app::buildGrid) — that is the RED state.

#include "../source/app/BuildGrid.h"
#include "../source/domain/ChordSpec.h"

#include <array>
#include <cstdio>
#include <cstdint>
#include <string>

using tuple::app::buildGrid;
using tuple::app::Grid;
using tuple::app::GridCell;
using tuple::app::kBorrowedSlots;
using tuple::app::kChordTypes;
using tuple::app::kDegrees;
using tuple::app::kMaxGridCells;
using tuple::domain::ChordSpec;

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

// A ChordSpec is valid by the same criteria ChordSpec::make() enforces
// (ChordSpec.cpp): a root pitch class 0..11, and a tone count in [1, 6].
// Every cell BuildGrid produces should pass this, whatever key/scaleIndex
// it was asked to build for (Task 6 Step 1 criterion: "aucune cellule ne
// porte un ChordSpec invalide").
bool isValidSpec (const ChordSpec& spec)
{
    return spec.rootPc <= 11 && spec.count >= 1 && spec.count <= tuple::domain::kMaxChordTones;
}

void checkGridInvariants (const Grid& grid, const char* label)
{
    expectTrue (grid.count <= kMaxGridCells,
                (std::string (label) + ": count never exceeds kMaxGridCells").c_str());

    bool sawDegree[kDegrees] = {};
    bool sawBorrowed = false;
    bool allValid = true;

    for (uint16_t i = 0; i < grid.count; ++i)
    {
        const GridCell& cell = grid.cells[i];

        if (! isValidSpec (cell.spec))
            allValid = false;

        if (cell.borrowed)
        {
            sawBorrowed = true;
        }
        else if (cell.degree < kDegrees)
        {
            sawDegree[cell.degree] = true;
        }
    }

    expectTrue (allValid, (std::string (label) + ": no cell carries an invalid ChordSpec").c_str());
    expectTrue (sawBorrowed, (std::string (label) + ": at least one borrowed cell is present").c_str());

    for (uint8_t degree = 0; degree < kDegrees; ++degree)
    {
        expectTrue (sawDegree[degree],
                    (std::string (label) + ": diatonic degree " + std::to_string (degree) + " is present").c_str());
    }
}

} // namespace

int main()
{
    // --- kMaxGridCells is derived, not a magic number -----------------------
    expectTrue (kMaxGridCells == static_cast<uint16_t> (kDegrees) * kChordTypes + kBorrowedSlots,
                "kMaxGridCells == kDegrees * kChordTypes + kBorrowedSlots");

    // --- C major: the ordinary case ------------------------------------------
    {
        const Grid grid = buildGrid (0, 0); // key = C, scaleIndex = Scale::Major
        checkGridInvariants (grid, "C major");
    }

    // --- a different key: roots must follow, not just degree 0 --------------
    {
        const Grid grid = buildGrid (7, 0); // key = G, scaleIndex = Scale::Major
        checkGridInvariants (grid, "G major");

        bool sawRootG = false;
        for (uint16_t i = 0; i < grid.count; ++i)
            if (! grid.cells[i].borrowed && grid.cells[i].degree == 0 && grid.cells[i].spec.rootPc == 7)
                sawRootG = true;
        expectTrue (sawRootG, "G major: degree I is rooted on G (pitch class 7), not C");
    }

    // --- a non-major scale: HarmonicMinor -------------------------------------
    {
        const Grid grid = buildGrid (0, 2); // scaleIndex = Scale::HarmonicMinor
        checkGridInvariants (grid, "C harmonic minor");
    }

    // --- an out-of-range key wraps via mod 12, never produces an invalid root
    {
        const Grid grid = buildGrid (255, 0);
        checkGridInvariants (grid, "key == 255 (wraps mod 12)");
    }

    // --- an out-of-range scaleIndex must not crash or invalidate cells -------
    {
        const Grid grid = buildGrid (0, 99);
        checkGridInvariants (grid, "scaleIndex == 99 (out of range, falls back)");
    }

    if (failures == 0)
    {
        std::printf ("\nAll grid tests passed.\n");
        return 0;
    }

    std::printf ("\n%d grid test(s) FAILED.\n", failures);
    return 1;
}
