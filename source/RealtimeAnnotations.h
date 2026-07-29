#pragma once

// The audio-thread contract, stated to the compiler instead of only to the
// reader (ARCHITECTURE.md §6: "Les contextes temps réel sont marqués
// [[clang::nonblocking]]").
//
// Lives at source/ root, above domain/app/plugin, on purpose: it is a
// compiler-contract header, not a layer. app/ needs it (releaseAll,
// decideTransportStop are called from the audio thread) and app/ must never
// include plugin/ — the Dependency Rule points inward.
//
// TUPLE_NONBLOCKING expands to `[[clang::nonblocking]]` on toolchains that
// actually implement the attribute, and to nothing anywhere else. That guard
// is not decoration: MSVC and any pre-20 Clang would otherwise emit an
// "unknown attribute" warning on every translation unit that includes this
// header, and windows-latest builds this plugin on every CI run.
//
// The attribute does TWO separate things, and they fail independently:
//
//   1. Compile time — Clang's function-effects analysis walks the call graph
//      below the annotated function and warns (-Wfunction-effects) about any
//      call it cannot prove non-blocking. It cannot see through virtual
//      dispatch, so calls into JUCE (e.g. AudioPlayHead::getPosition()) are
//      expected to warn. A warning there is "unproven", not "proven unsafe".
//
//   2. Run time — Clang emits __rtsan_realtime_enter/__rtsan_realtime_exit
//      around the function body, which is what actually puts
//      RealtimeSanitizer into real-time context. THIS is the part that can
//      flag a genuine allocation/syscall/lock in Tuple's own code, and it is
//      the reason the annotation exists at all. Suppressing (1) locally never
//      disables (2).
//
// Placement is a SUFFIX, after the parameter list and before `override`:
// [[clang::nonblocking]] is a function-TYPE attribute (like noexcept), not a
// declaration attribute. A prefix placement is rejected by the compiler
// (verified 2026-07-29 against LLVM 22.1.8). Being part of the type, it must
// appear on the declaration AND the definition or they name different types.

#if defined(__has_cpp_attribute)
  #if __has_cpp_attribute(clang::nonblocking)
    #define TUPLE_NONBLOCKING [[clang::nonblocking]]
    #define TUPLE_NONBLOCKING_SUPPORTED 1
  #endif
#endif

#if !defined(TUPLE_NONBLOCKING)
  #define TUPLE_NONBLOCKING
  #define TUPLE_NONBLOCKING_SUPPORTED 0
#endif

// A RealtimeSanitizer build whose annotations silently evaporated is worse
// than no sanitizer build: every check downstream goes green while nothing is
// ever in real-time context. TUPLE_RTSAN is defined by CMakeLists.txt only in
// the -DTUPLE_RTSAN=ON branch, so this is a hard stop on exactly that case.
#if defined(TUPLE_RTSAN) && TUPLE_NONBLOCKING_SUPPORTED == 0
  #error "TUPLE_RTSAN=ON but this toolchain does not implement [[clang::nonblocking]] (Clang >= 20 required). The sanitizer would link in and flag nothing. Refusing to build a green-but-empty RTSan binary."
#endif
