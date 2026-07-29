#include "Voicing.h"

namespace tuple::domain {

namespace {

// The nearest placement of a pitch class to `centre`, as a signed offset from
// `centre` in {-5, ..., 6} (twelve possible values, one per residue). This is
// the ONE comparison that decides "the octave above centre is closer" vs
// "the octave below is closer" — Task 3 Step 4's witness bug inverts exactly
// this comparison (distUp <= distDown -> distUp >= distDown), which sends
// almost every tone to the far octave instead of the near one.
int nearestOffset (int pc, int centre)
{
    const int diff = ((pc - centre) % 12 + 12) % 12; // 0..11: semitones UP from centre to reach pc
    const int distUp   = diff;
    const int distDown = 12 - diff;
    return (distUp <= distDown) ? diff : (diff - 12);
}

// Brings a note into 0..127 by octave-correcting (+-12) rather than clamping
// to the boundary value. This matters: clamping a too-low note straight to 0
// (or a too-high one to 127) fabricates a specific pitch class the tone never
// actually had, which can collide with the chord's root and silently break
// Rootless's "never contains the root's pitch class" invariant. A +-12
// correction preserves pitch class exactly. The offsets `realize()` ever
// produces are always within one octave of 0..127's edges for a valid
// (0..127) `centre`, so one correction per direction always suffices; the
// final clamp is a defensive fallback that should never trigger.
uint8_t placeInMidiRange (int note)
{
    if (note < 0)   note += 12;
    if (note > 127) note -= 12;
    if (note < 0)   note = 0;
    if (note > 127) note = 127;
    return static_cast<uint8_t> (note);
}

// The one voice Drop targets, by role priority (Seventh, else Third, else
// Fifth), Root excluded. A bag of bare semitones could not answer "which one
// is the seventh" — this is why ChordSpec carries roles (Task 2 rationale).
bool findDropTarget (const ChordSpec& spec, uint8_t& outSemitones)
{
    for (Role priority : { Role::Seventh, Role::Third, Role::Fifth })
    {
        for (uint8_t i = 0; i < spec.count; ++i)
        {
            if (spec.tones[i].role == priority)
            {
                outSemitones = spec.tones[i].semitones;
                return true;
            }
        }
    }
    return false;
}

} // namespace

RealizedChord realize (const ChordSpec& spec, VoicingFamily family, const VoicingSettings& settings)
{
    (void) settings.openness; // Phase 0 placeholder: accepted for API stability, unused (see Voicing.h).
    (void) settings.density;

    const int centre = settings.centre;

    uint8_t dropTargetSemitones = 0;
    const bool hasDropTarget = findDropTarget (spec, dropTargetSemitones);

    RealizedChord result {};
    result.count = 0;

    for (uint8_t i = 0; i < spec.count; ++i)
    {
        const ChordTone& tone = spec.tones[i];

        if (family == VoicingFamily::Rootless && tone.role == Role::Root)
            continue; // "Rootless doit retirer la fondamentale" (Task 3)

        const int pc = (spec.rootPc + tone.semitones) % 12;
        int offset = nearestOffset (pc, centre);

        switch (family)
        {
            case VoicingFamily::Close:
            case VoicingFamily::Rootless:
                break; // base placement only; Rootless already skipped the root above

            case VoicingFamily::Open:
                // Push any non-root tone that landed below centre back above
                // it, widening the voicing (matches fixtures/voicing_basic.txt).
                if (tone.role != Role::Root && offset < 0)
                    offset += 12;
                break;

            case VoicingFamily::Drop:
                // Descend the one targeted voice, and only if it is currently
                // above centre — dropping an already-low voice further would
                // break the "within 12 semitones of centre" invariant.
                if (hasDropTarget && tone.semitones == dropTargetSemitones && offset > 0)
                    offset -= 12;
                break;

            case VoicingFamily::Quartal:
                // Naive placeholder spacing: every upper voice (not just the
                // one Drop targets) descends. Not real quartal harmony —
                // Phase 0 does not reharmonize by fourths.
                if (tone.role != Role::Root && offset > 0)
                    offset -= 12;
                break;

            case VoicingFamily::TwoHand:
                // Low root (left hand), chord close to centre (right hand) —
                // the two-handed piano mode (CLAUDE.md).
                if (tone.role == Role::Root && offset > 0)
                    offset -= 12;
                break;
        }

        result.notes[result.count++] = placeInMidiRange (centre + offset);
    }

    return result;
}

} // namespace tuple::domain
