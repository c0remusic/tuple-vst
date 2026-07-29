// Voicing test binary (Task 3, docs/plans/2026-07-29-phase-0-squelette.md).
// No JUCE, no third-party framework — same self-contained runner style as
// tests/domain_tests.cpp (ARCHITECTURE.md §1: starts in about a second).
//
// Task 3, Step 1: written and run BEFORE Voicing.cpp exists. At this point
// source/domain/Voicing.cpp has been moved aside, so this binary is expected
// to fail to LINK (undefined reference to tuple::domain::realize) — that is
// the RED state.

#include "../source/domain/ChordSpec.h"
#include "../source/domain/Voicing.h"
#include "../source/domain/VoicingFamily.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using tuple::domain::ChordSpec;
using tuple::domain::ChordTone;
using tuple::domain::realize;
using tuple::domain::RealizedChord;
using tuple::domain::Role;
using tuple::domain::VoicingFamily;
using tuple::domain::VoicingSettings;

namespace {

int failures = 0;

void expectTrue (bool condition, const std::string& description)
{
    if (condition)
    {
        std::printf ("[PASS] %s\n", description.c_str());
    }
    else
    {
        std::printf ("[FAIL] %s\n", description.c_str());
        ++failures;
    }
}

std::vector<uint8_t> notesOf (const RealizedChord& chord)
{
    return { chord.notes.begin(), chord.notes.begin() + chord.count };
}

bool operator== (const RealizedChord& a, const RealizedChord& b)
{
    return notesOf (a) == notesOf (b);
}

std::string toString (const std::vector<uint8_t>& notes)
{
    std::string s = "{";
    for (size_t i = 0; i < notes.size(); ++i)
    {
        if (i != 0) s += ",";
        s += std::to_string (static_cast<int> (notes[i]));
    }
    s += "}";
    return s;
}

void expectNotes (const RealizedChord& actual, const std::vector<uint8_t>& expected, const std::string& description)
{
    auto got = notesOf (actual);
    if (got == expected)
    {
        std::printf ("[PASS] %s\n", description.c_str());
    }
    else
    {
        std::printf ("[FAIL] %s (got %s, expected %s)\n",
                      description.c_str(), toString (got).c_str(), toString (expected).c_str());
        ++failures;
    }
}

VoicingSettings settingsAt (uint8_t centre)
{
    return VoicingSettings { 0.5f, 0.5f, centre };
}

const std::array<VoicingFamily, 6> kAllFamilies {
    VoicingFamily::Close, VoicingFamily::Open, VoicingFamily::Drop,
    VoicingFamily::Rootless, VoicingFamily::Quartal, VoicingFamily::TwoHand
};

ChordSpec majorTriad()  { return *ChordSpec::make (0, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth } }); }
ChordSpec minorTriad()  { return *ChordSpec::make (0, { { 0, Role::Root }, { 3, Role::Third }, { 7, Role::Fifth } }); }
ChordSpec dominant7()   { return *ChordSpec::make (0, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth }, { 10, Role::Seventh } }); }

} // namespace

int main()
{
    // --- Known values at centre=60 (the two given in the plan itself) -----
    {
        auto spec = majorTriad();
        expectNotes (realize (spec, VoicingFamily::Close, settingsAt (60)), { 60, 64, 55 },
                     "Close(major triad, centre=60) == {60,64,55} (plan example)");
        expectNotes (realize (spec, VoicingFamily::Open, settingsAt (60)), { 60, 64, 67 },
                     "Open(major triad, centre=60) == {60,64,67} (plan example)");
    }

    // --- Drop targets a SPECIFIC voice, by role, not "second from top" ----
    // centre=30 is chosen so the dropped voice's -12 shift lands safely
    // above 0 (no octave re-correction that would undo the drop).
    {
        auto spec = dominant7();
        expectNotes (realize (spec, VoicingFamily::Close, settingsAt (30)), { 36, 28, 31, 34 },
                     "Close(dominant7, centre=30) == {36,28,31,34}");
        expectNotes (realize (spec, VoicingFamily::Drop, settingsAt (30)), { 36, 28, 31, 22 },
                     "Drop(dominant7, centre=30) descends ONLY the seventh, to {36,28,31,22}");
        expectNotes (realize (spec, VoicingFamily::Quartal, settingsAt (30)), { 36, 28, 19, 22 },
                     "Quartal(dominant7, centre=30) descends every upper voice, to {36,28,19,22}");
        expectNotes (realize (spec, VoicingFamily::TwoHand, settingsAt (30)), { 24, 28, 31, 34 },
                     "TwoHand(dominant7, centre=30) descends only the root, to {24,28,31,34}");
        expectNotes (realize (spec, VoicingFamily::Rootless, settingsAt (30)), { 28, 31, 34 },
                     "Rootless(dominant7, centre=30) drops the root entirely, to {28,31,34}");
    }

    // --- Rootless never contains the pitch class of the Root role ---------
    for (uint8_t centre : { 0, 1, 40, 60, 90, 126, 127 })
    {
        for (auto spec : { majorTriad(), minorTriad(), dominant7() })
        {
            auto result = realize (spec, VoicingFamily::Rootless, settingsAt (centre));
            bool containsRootPc = false;
            for (uint8_t i = 0; i < result.count; ++i)
                if (result.notes[i] % 12 == spec.rootPc)
                    containsRootPc = true;
            expectTrue (! containsRootPc,
                        "Rootless(rootPc=" + std::to_string (spec.rootPc) +
                        ", centre=" + std::to_string ((int) centre) + ") excludes the root's pitch class");
        }
    }

    // --- General sweep: every note within 0..127 and within 12 of centre,
    //     and calling realize() twice with the same inputs is deterministic.
    for (uint8_t centre : { 0, 1, 6, 40, 60, 90, 126, 127 })
    {
        for (auto family : kAllFamilies)
        {
            for (auto spec : { majorTriad(), minorTriad(), dominant7() })
            {
                auto settings = settingsAt (centre);
                auto a = realize (spec, family, settings);
                auto b = realize (spec, family, settings);

                expectTrue (a == b, "realize() is deterministic (same spec/family/settings twice)");

                for (uint8_t i = 0; i < a.count; ++i)
                {
                    int note = a.notes[i];
                    expectTrue (note >= 0 && note <= 127,
                                "note " + std::to_string (note) + " is within 0..127");
                    int distance = note - static_cast<int> (centre);
                    if (distance < 0) distance = -distance;
                    expectTrue (distance < 12,
                                "note " + std::to_string (note) + " is within 12 semitones of centre " +
                                std::to_string ((int) centre) + " (distance " + std::to_string (distance) + ")");
                }
            }
        }
    }

    // --- The six families are not all a no-op: at least two distinct
    //     dispositions for the same spec. -----------------------------------
    for (auto spec : { majorTriad(), minorTriad(), dominant7() })
    {
        std::vector<std::vector<uint8_t>> dispositions;
        for (auto family : kAllFamilies)
            dispositions.push_back (notesOf (realize (spec, family, settingsAt (60))));

        bool allIdentical = true;
        for (const auto& d : dispositions)
            if (d != dispositions.front())
                allIdentical = false;

        expectTrue (! allIdentical,
                    "the six families do not all produce the same disposition (rootPc=" +
                    std::to_string (spec.rootPc) + ")");
    }

    // --- fixtures/voicing_basic.txt: the format is the specification ------
    // Task 3, Step 5. This block must FAIL if the file is missing or empty —
    // otherwise it would pass for the wrong reason (nothing was checked).
    {
#ifdef TUPLE_FIXTURES_DIR
        const std::string path = std::string (TUPLE_FIXTURES_DIR) + "/voicing_basic.txt";
#else
        const std::string path = "fixtures/voicing_basic.txt";
#endif
        std::ifstream file (path);
        expectTrue (file.is_open(), "fixtures/voicing_basic.txt opens at '" + path + "'");

        int dataLines = 0;
        std::string line;
        while (file.good() && std::getline (file, line))
        {
            // Strip a trailing '\r' in case the file is read on a platform
            // that does not translate CRLF, and skip blank/comment lines.
            if (! line.empty() && line.back() == '\r')
                line.pop_back();
            if (line.empty() || line[0] == '#')
                continue;

            // Format: rootPc | tones (semitones:role,...) | family | centre | notes
            std::vector<std::string> fields;
            {
                std::stringstream ss (line);
                std::string field;
                while (std::getline (ss, field, '|'))
                    fields.push_back (field);
            }
            expectTrue (fields.size() == 5, "fixture line has 5 '|'-separated fields: " + line);
            if (fields.size() != 5)
                continue;

            auto trim = [] (std::string s)
            {
                size_t start = s.find_first_not_of (" \t");
                size_t end   = s.find_last_not_of (" \t");
                if (start == std::string::npos) return std::string();
                return s.substr (start, end - start + 1);
            };

            uint8_t rootPc = static_cast<uint8_t> (std::stoi (trim (fields[0])));

            std::vector<ChordTone> tones;
            {
                std::stringstream ts (trim (fields[1]));
                std::string tone;
                while (std::getline (ts, tone, ','))
                {
                    tone = trim (tone);
                    size_t colon = tone.find (':');
                    uint8_t semitones = static_cast<uint8_t> (std::stoi (tone.substr (0, colon)));
                    std::string roleName = tone.substr (colon + 1);
                    Role role;
                    if (roleName == "Root") role = Role::Root;
                    else if (roleName == "Third") role = Role::Third;
                    else if (roleName == "Fifth") role = Role::Fifth;
                    else if (roleName == "Seventh") role = Role::Seventh;
                    else if (roleName == "Ninth") role = Role::Ninth;
                    else if (roleName == "Eleventh") role = Role::Eleventh;
                    else if (roleName == "Thirteenth") role = Role::Thirteenth;
                    else if (roleName == "Sus") role = Role::Sus;
                    else { expectTrue (false, "unknown role name in fixture: " + roleName); continue; }
                    tones.push_back ({ semitones, role });
                }
            }

            std::string familyName = trim (fields[2]);
            VoicingFamily family;
            if (familyName == "Close") family = VoicingFamily::Close;
            else if (familyName == "Open") family = VoicingFamily::Open;
            else if (familyName == "Drop") family = VoicingFamily::Drop;
            else if (familyName == "Rootless") family = VoicingFamily::Rootless;
            else if (familyName == "Quartal") family = VoicingFamily::Quartal;
            else if (familyName == "TwoHand") family = VoicingFamily::TwoHand;
            else { expectTrue (false, "unknown family name in fixture: " + familyName); continue; }

            uint8_t centre = static_cast<uint8_t> (std::stoi (trim (fields[3])));

            std::vector<uint8_t> expectedNotes;
            {
                std::stringstream ns (trim (fields[4]));
                std::string n;
                while (std::getline (ns, n, ','))
                    expectedNotes.push_back (static_cast<uint8_t> (std::stoi (trim (n))));
            }

            // ChordSpec::make() only accepts a literal std::initializer_list,
            // which a runtime-sized std::vector cannot construct into — so a
            // fixture-driven ChordSpec is built directly. Its fields are
            // plain public data (Task 2); tone count is still bounds-checked.
            expectTrue (! tones.empty() && tones.size() <= tuple::domain::kMaxChordTones,
                        "fixture line has 1.." + std::to_string ((int) tuple::domain::kMaxChordTones) +
                        " tones: " + line);
            if (tones.empty() || tones.size() > tuple::domain::kMaxChordTones)
                continue;

            ChordSpec spec {};
            spec.rootPc = rootPc;
            spec.count = static_cast<uint8_t> (tones.size());
            for (size_t i = 0; i < tones.size(); ++i)
                spec.tones[i] = tones[i];

            auto result = realize (spec, family, settingsAt (centre));
            expectNotes (result, expectedNotes, "fixture: " + line);
            ++dataLines;
        }

        expectTrue (dataLines >= 18,
                    "fixtures/voicing_basic.txt has at least 18 data lines (found " +
                    std::to_string (dataLines) + ")");
    }

    if (failures == 0)
    {
        std::printf ("\nAll voicing tests passed.\n");
        return 0;
    }

    std::printf ("\n%d voicing test(s) FAILED.\n", failures);
    return 1;
}
