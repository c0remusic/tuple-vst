// Task 5 invariant + MidiEmitter offset tests
// (docs/plans/2026-07-29-phase-0-squelette.md). No third-party framework,
// same self-contained runner style as tests/domain_tests.cpp /
// tests/voicing_tests.cpp.
//
// Task 5, Step 1: written and run BEFORE source/app/PlayChord.cpp,
// source/app/ReleaseAll.cpp, and source/plugin/MidiEmitter.cpp exist. At
// this point CMakeLists' NoteoffTests target does not list those three
// .cpp files, so this binary is expected to fail to LINK (undefined
// reference to tuple::app::playChord, tuple::app::releaseAll, and
// tuple::plugin::emit) — that is the RED state.

#include "../source/app/PlayChord.h"
#include "../source/app/ReleaseAll.h"
#include "../source/app/TransportStop.h"
#include "../source/domain/ChordSpec.h"
#include "../source/domain/VoicingFamily.h"
#include "../source/plugin/MidiEmitter.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <string>

#include <juce_audio_basics/juce_audio_basics.h>

using tuple::app::ChordRequest;
using tuple::app::decideTransportStop;
using tuple::app::kDefaultVelocity;
using tuple::app::NoteBatch;
using tuple::app::playChord;
using tuple::app::releaseAll;
using tuple::domain::ChordSpec;
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

// --- shared fixtures ---------------------------------------------------

VoicingSettings settingsAt (uint8_t centre) { return VoicingSettings { 0.5f, 0.5f, centre }; }

ChordSpec chordA() { return *ChordSpec::make (0, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth } }); }                          // C major
ChordSpec chordB() { return *ChordSpec::make (2, { { 0, Role::Root }, { 3, Role::Third }, { 7, Role::Fifth } }); }                          // D minor
ChordSpec chordC() { return *ChordSpec::make (7, { { 0, Role::Root }, { 4, Role::Third }, { 7, Role::Fifth }, { 10, Role::Seventh } }); }   // G dominant 7

// --- note-off invariant tracker -----------------------------------------
// Tracks, per MIDI pitch, whether a note is CURRENTLY sounding. Applying a
// batch walks its events IN ORDER — playChord's batches are offs-then-ons on
// purpose (Task 5), so a pitch shared between the outgoing and incoming
// chord is released before it is re-triggered, never the reverse.
class NoteOffTracker
{
public:
    void apply (const NoteBatch& batch)
    {
        for (uint8_t i = 0; i < batch.count; ++i)
        {
            const auto& event = batch.events[i];
            if (event.velocity == 0)
            {
                expectTrue (onFlags_[event.pitch],
                            "pitch " + std::to_string ((int) event.pitch) +
                            " gets a note-off only while it is sounding");
                onFlags_[event.pitch] = false;
            }
            else
            {
                expectTrue (! onFlags_[event.pitch],
                            "pitch " + std::to_string ((int) event.pitch) +
                            " does not get a second note-on while already sounding");
                onFlags_[event.pitch] = true;
            }
        }
    }

    // The invariant itself: every note-on this tracker has seen must, by the
    // time this is called, have a matching note-off.
    bool allReleased() const
    {
        for (bool on : onFlags_)
            if (on)
                return false;
        return true;
    }

private:
    std::array<bool, 128> onFlags_ {};
};

// playChord() returns priorSounding.count offs followed by the new chord's
// ons, in that exact order (Task 5 rationale) — so the new sounding state is
// always the tail of the returned batch, starting right after where the offs
// ended.
NoteBatch soundingAfter (uint8_t priorSoundingCount, const NoteBatch& played)
{
    NoteBatch out {};
    out.count = 0;
    for (uint8_t i = priorSoundingCount; i < played.count; ++i)
        out.events[out.count++] = played.events[i];
    return out;
}

// Shared prefix for all four trigger scenarios below: nothing sounding ->
// chordA sounding -> chordB sounding. The SECOND playChord call is the one
// that must emit chordA's note-offs alongside chordB's note-ons — exactly
// what Step 4's witness bug removes. That is why all four scenarios go red
// TOGETHER when it is introduced: chordA's notes are never released by any
// of the four trigger paths, since playChord is the only place that would
// ever have emitted them.
NoteBatch primeChordBSounding (NoteOffTracker& tracker)
{
    NoteBatch empty {};
    empty.count = 0;

    ChordRequest reqA { chordA(), VoicingFamily::Close, settingsAt (60), 0 };
    auto batchA = playChord (reqA, empty);
    tracker.apply (batchA);
    auto soundingA = soundingAfter (0, batchA);

    ChordRequest reqB { chordB(), VoicingFamily::Open, settingsAt (60), 40 };
    auto batchB = playChord (reqB, soundingA);
    tracker.apply (batchB);
    return soundingAfter (soundingA.count, batchB);
}

} // namespace

int main()
{
    // --- Trigger 1: changement d'accord -------------------------------
    {
        NoteOffTracker tracker;
        auto soundingB = primeChordBSounding (tracker);

        ChordRequest reqC { chordC(), VoicingFamily::Drop, settingsAt (60), 80 };
        auto batchC = playChord (reqC, soundingB);
        tracker.apply (batchC);
        auto soundingC = soundingAfter (soundingB.count, batchC);

        // Close the session so the check below is a clean "nothing left
        // sounding". The assertion this scenario is actually about — that
        // chordB's notes got released when chordC replaced it — is already
        // checked inside tracker.apply(batchC) above (its per-event
        // "no note-off without a prior note-on" / "no second note-on while
        // sounding" checks).
        tracker.apply (releaseAll (soundingC, 120));

        expectTrue (tracker.allReleased(),
                    "Trigger 1 (changement d'accord): every note-on across two chord changes gets exactly one note-off");
    }

    // --- Trigger 2: arret du transport ----------------------------------
    {
        NoteOffTracker tracker;
        auto soundingB = primeChordBSounding (tracker);

        // Simulates PluginProcessor::processBlock() noticing the transport
        // just stopped (Task 5 Step 6) and releasing whatever is sounding.
        tracker.apply (releaseAll (soundingB, 96));

        expectTrue (tracker.allReleased(),
                    "Trigger 2 (arret du transport): releaseAll() on transport stop clears every sounding note-on");
    }

    // --- Regression: front descendant sur un bloc de 0 echantillon --------
    // A zero-sample processBlock() call landing EXACTLY on the transport's
    // falling edge has no valid sample to place a note-off at. The bug: the
    // old inline logic in processBlock() advanced wasPlaying unconditionally
    // regardless of whether the release actually happened, which erased the
    // edge forever -- "wasPlaying && !isPlayingNow" could never fire again
    // for that stop, so the note-off was LOST, not delayed. This exercises
    // decideTransportStop() directly (extracted so this is testable without
    // a JUCE host), across three simulated blocks: playing with notes
    // sounding -> a 0-sample block at the falling edge -> a normal block
    // still stopped.
    {
        NoteOffTracker tracker;
        auto soundingB = primeChordBSounding (tracker);
        bool wasPlaying = true; // matches the state primeChordBSounding leaves the transport in

        // Block N: transport just stopped, but the host hands us an EMPTY
        // buffer. No valid sample offset exists -- nothing may be emitted.
        auto firstEdge = decideTransportStop (wasPlaying, /*isPlayingNow*/ false, soundingB.count, /*numSamples*/ 0);
        expectTrue (! firstEdge.shouldRelease,
                    "regression: a 0-sample block at the falling edge must not attempt a release");
        expectTrue (! firstEdge.advanceWasPlaying,
                    "regression: a 0-sample block at the falling edge must NOT consume it (fix: stay armed)");
        if (firstEdge.advanceWasPlaying)
            wasPlaying = false; // faithfully replays what processBlock() does with the decision

        // Block N+1: still stopped, this time with a normal buffer. If the
        // edge survived (the fix), it must fire here -- this is the ONLY
        // chance left to release chordB's notes.
        constexpr int kNumSamples = 512;
        auto secondEdge = decideTransportStop (wasPlaying, /*isPlayingNow*/ false, soundingB.count, kNumSamples);
        expectTrue (secondEdge.shouldRelease,
                    "regression: the falling edge must still be armed on the next block and fire there");

        if (secondEdge.shouldRelease)
            tracker.apply (releaseAll (soundingB, kNumSamples - 1));

        expectTrue (tracker.allReleased(),
                    "regression: the note-off is eventually emitted -- every note-on still gets exactly one note-off");
    }

    // --- decideTransportStop(): decision table, independent of the above ---
    {
        // Not at the falling edge (still playing): never release, always
        // free to advance -- there is no edge to lose here.
        auto stillPlaying = decideTransportStop (/*wasPlaying*/ true, /*isPlayingNow*/ true, /*soundingCount*/ 3, /*numSamples*/ 256);
        expectTrue (! stillPlaying.shouldRelease, "decideTransportStop: no release while transport keeps playing");
        expectTrue (stillPlaying.advanceWasPlaying, "decideTransportStop: always safe to advance when not at the edge");

        // Nothing sounding when the transport stops: no release needed, no
        // edge to preserve either.
        auto nothingSounding = decideTransportStop (/*wasPlaying*/ true, /*isPlayingNow*/ false, /*soundingCount*/ 0, /*numSamples*/ 256);
        expectTrue (! nothingSounding.shouldRelease, "decideTransportStop: no release when nothing is sounding");
        expectTrue (nothingSounding.advanceWasPlaying, "decideTransportStop: safe to advance when nothing is sounding");

        // The exact regression case, in isolation.
        auto zeroSampleEdge = decideTransportStop (/*wasPlaying*/ true, /*isPlayingNow*/ false, /*soundingCount*/ 3, /*numSamples*/ 0);
        expectTrue (! zeroSampleEdge.shouldRelease, "decideTransportStop: a 0-sample block at the edge never releases");
        expectTrue (! zeroSampleEdge.advanceWasPlaying, "decideTransportStop: a 0-sample block at the edge stays armed");

        // The normal, already-covered case: non-empty block at the edge.
        auto normalEdge = decideTransportStop (/*wasPlaying*/ true, /*isPlayingNow*/ false, /*soundingCount*/ 3, /*numSamples*/ 256);
        expectTrue (normalEdge.shouldRelease, "decideTransportStop: a normal block at the edge releases");
        expectTrue (normalEdge.advanceWasPlaying, "decideTransportStop: a normal block at the edge consumes it");
    }

    // --- Trigger 3: releaseResources --------------------------------------
    {
        NoteOffTracker tracker;
        auto soundingB = primeChordBSounding (tracker);

        // Simulates PluginProcessor::releaseResources() (Task 5 Step 6):
        // the same releaseAll() as Trigger 2, exercised as its OWN test
        // case because it is a distinct call site the plan requires
        // covered on its own (Global Constraints: four triggers, one test
        // case each).
        tracker.apply (releaseAll (soundingB, 0));

        expectTrue (tracker.allReleased(),
                    "Trigger 3 (releaseResources): releaseAll() clears every sounding note-on");
    }

    // --- Trigger 4: destruction du plugin ----------------------------------
    {
        NoteOffTracker tracker;
        auto soundingB = primeChordBSounding (tracker);

        // Simulates ~TupleProcessor() (Task 5 Step 6): the same releaseAll()
        // as Triggers 2/3, exercised as its own test case for the same
        // reason. A real host MIDI buffer no longer exists at destruction
        // time, so what IS testable and guaranteed here is that this pure
        // function correctly accounts for every sounding note when called
        // from that site.
        tracker.apply (releaseAll (soundingB, 0));

        expectTrue (tracker.allReleased(),
                    "Trigger 4 (destruction du plugin): releaseAll() clears every sounding note-on");
    }

    // --- MidiEmitter: events land at THEIR OWN sample offset, never at 0 --
    {
        NoteBatch batch {};
        batch.count = 2;
        batch.events[0] = { 60, kDefaultVelocity, 128 }; // note-on at sample 128
        batch.events[1] = { 60, 0, 128 };                // note-off at sample 128

        juce::MidiBuffer buffer;
        tuple::plugin::emit (batch, buffer);

        expectTrue (buffer.getNumEvents() == 2, "MidiEmitter emits both events from the batch");

        int countAt128 = 0;
        int countAtZero = 0;
        for (const auto metadata : buffer)
        {
            if (metadata.samplePosition == 128) ++countAt128;
            if (metadata.samplePosition == 0) ++countAtZero;
        }
        expectTrue (countAt128 == 2, "MidiEmitter places both sampleOffset=128 events at buffer position 128");
        expectTrue (countAtZero == 0, "MidiEmitter never collapses a non-zero sampleOffset to buffer position 0");
    }

    if (failures == 0)
    {
        std::printf ("\nAll note-off tests passed.\n");
        return 0;
    }

    std::printf ("\n%d note-off test(s) FAILED.\n", failures);
    return 1;
}
