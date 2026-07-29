#pragma once

#include <array>
#include <cstdint>

#include "../domain/ChordSpec.h"

namespace tuple::app {

// --- Grid shape, derived from named constants (Task 6, Global Constraints:
// "la taille est derivee de constantes nommees, jamais un nombre magique") --

// The seven diatonic scale degrees (PRD.md §6: "Colonnes : les sept degres").
inline constexpr uint8_t kDegrees = 7;

// The fixed catalogue of chord-quality templates BuildGrid.cpp builds on
// every degree (PRD.md §6: "Lignes : les types d'accord"). See
// BuildGrid.cpp's anonymous-namespace `chordType()` for the actual 12
// templates and why this count is naive-but-deterministic for Phase 0.
inline constexpr uint8_t kChordTypes = 12;

// The borrowed-chord region (PRD.md §3.2, §6: borrowed chords stay inside
// the main grid, never behind a menu). One slot per chromatic pitch class.
inline constexpr uint8_t kBorrowedSlots = 12;

// kDegrees * kChordTypes diatonic cells, plus kBorrowedSlots borrowed cells.
inline constexpr uint16_t kMaxGridCells =
    static_cast<uint16_t> (kDegrees) * static_cast<uint16_t> (kChordTypes) + kBorrowedSlots;

// One cell of the grid: a chord, which diatonic degree it was built on (or,
// for a borrowed cell, an opaque pitch-class slot index — see buildGrid()'s
// borrowed-region comment), and whether it is borrowed.
struct GridCell
{
    tuple::domain::ChordSpec spec;
    uint8_t degree;
    bool borrowed;
};

// A fixed-size grid, returned by copy — no heap, no std::vector (Global
// Constraints, "la regle la plus facile a casser"). `count` is always
// <= kMaxGridCells; Phase 0's implementation always fills every cell, so in
// practice count == kMaxGridCells, but callers must not assume that.
struct Grid
{
    std::array<GridCell, kMaxGridCells> cells;
    uint16_t count;
};

// Builds the full grid for `key` (pitch class, taken mod 12 so any uint8_t is
// accepted) and `scaleIndex` (a tuple::domain::Scale value; an out-of-range
// index falls back to Scale::Major rather than producing an invalid cell —
// see BuildGrid.cpp). Every diatonic degree gets one cell per chord-quality
// template; the borrowed region adds one cell per chromatic pitch class.
// Aucune allocation.
Grid buildGrid (uint8_t key, uint8_t scaleIndex);

} // namespace tuple::app
