# Independent review of the color prototype

Reviewed 2026-10-07 against application prototype `48231d21` and the combined
preview/reference verification in `a0405899`. The review covered the export
filter, sampled curve and provenance, shader texture packing and alpha handling,
processing order, neutral bypass, errors, project/preset/queue persistence,
export markers, application/settings/update identities, staging and notices.

## Findings fixed

1. **Incomplete development source snapshots.** Development staging previously
   permitted a dirty checkout, then archived HEAD and saved a tracked-file diff.
   Newly added, untracked source was omitted from both. A disposable packaging
   fixture reproduced this. All staging now requires committed source, including
   development runtimes. This avoids silently omitting source or archiving
   private untracked files. Dirty-source patch generation was removed.
2. **False external dependencies for universal Mac binaries.** The dependency
   audit treated later architecture-header filenames from `otool -L` as library
   dependencies. It now reads only indented versioned dependency records and
   still reports genuine absolute non-system libraries. A synthetic universal
   output fixture verifies that architecture headers are excluded.

Both focused packaging tests pass with Python's standard-library unittest.
These fixes do not change the compiled color/rendering paths or their timing.

## Evidence accepted, with limits

- The 16 parser/filter/curve tests include the earlier ownership, alpha,
  ten-bit, stride, color-property and neutral-path checks.
- The independent OpenColorIO CPU comparison and production Metal shader
  comparisons are documented in [the prototype report](COLOR-TONE-PROTOTYPE.md).
  The bounded sampled curve is an approximation, not the full OCIO runtime.
- For the tested moving section, all 481 neutral frames and timestamps match
  the earlier export. Color output differs by at most one ten-bit value from
  the independent reference. This does not establish equivalence for every
  codec, color space or recording.
- The one-second 4K measurements show modest added tone overhead, with the
  hardware-encoding option retained. They are not a full-flight speed guarantee.
- Original recording and official-app preservation checks passed. Separate
  settings and update identities prevent the fork from updating official
  Gyroflow or using its Store/WinGet release automation.

## Remaining acceptance gates

Native video loading in the separately staged development bundle stalls in the
operating system's file-open call. The cause is unconfirmed; a normal macOS
access prompt is possible. Computer use refused access to the protected system
prompt. Resolve this through normal OS handling before claiming playback,
slider gestures, GUI save/restart, queue acceptance or installation readiness.
The earlier LUT Preview app remains intact.

Windows runtime validation of the new controls and portable public releases
remain open. Dependency closure, licensing, clean-machine tests and signing
gates are in [the distribution plan](PLUS-DISTRIBUTION.md). Do not label the
development bundle a portable or publicly released installer.
