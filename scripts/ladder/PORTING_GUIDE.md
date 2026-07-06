# Importing a classic Robocode bot into the CodeClash arena

This arena is **classic Robocode** (Java, `robocode.jar`), NOT Tank Royale. Importing an
open-source classic bot is mostly a mechanical **copy-in + rename**, not a strategy rewrite.

## The submission contract
The submission is a directory `robots/custom/` containing Java source. The arena harness then:
1. copies `robots/custom/*` into `robots/<player>/`,
2. runs `sed 's/custom/<player>/g'` over every `.java` (this renames the `package custom` →
   `package <player>` so bots are namespaced),
3. compiles `javac -cp "libs/robocode.jar" robots/<player>/*.java`  ← **flat glob, one directory**,
4. runs battles selecting `<player>.MyTank*`.

`validate_code` requires `robots/custom/MyTank.java` to exist, compile, and produce `MyTank.class`.

## Hard rules for a port (`ports/<slug>/`)
Produce a directory `scripts/ladder/ports/<slug>/` containing:
- **`MyTank.java`** — the bot's main class, **renamed to `public class MyTank`** (rename the source's
  main class everywhere: declaration, constructors, and any self-references). It must
  `extends robocode.Robot` (or `AdvancedRobot` / `TeamRobot` / `RateControlRobot` / `JuniorRobot`).
- **`package custom;`** as the package line in `MyTank.java` and in *every* helper file. Replace any
  original `package a.b.c;`.
- **Helper classes** (if the bot is multi-file) as additional flat `.java` files in the same dir,
  also `package custom;`. **No nested subdirectories** — the compile is a flat `*.java` glob, so a
  bot that uses nested packages (e.g. `voidious/gun/…`) must be flattened or it won't compile.
  Inner classes inside one file are fine (preferred).
- **The literal substring `custom` must NOT appear anywhere except the `package custom;` lines.**
  The harness's `sed s/custom/<player>/g` is a blind global replace, so any identifier, comment, or
  string containing "custom" would be corrupted. Rename such tokens.

## What's allowed / what breaks
- Only the classic `robocode.*` API. No Tank Royale (`dev.robocode.tankroyale.*`).
- Robocode runs under a security manager: **raw `java.io`, threads, reflection, and network are
  blocked.** Persistent gun/enemy stats via the sanctioned `getDataFile()` +
  `RobocodeFileOutputStream` are allowed but **may not persist** across our battles — such a bot
  still compiles and plays, it just degrades to no saved data (fine; note it). If the source uses
  raw `java.io`/threads/reflection, it will fail — flag and skip, or strip that path if it's optional.
- Keep behavior faithful: do not "improve" the bot; only rename/repackage/flatten.

## Deliverable + report
Write the port dir `scripts/ladder/ports/<slug>/` (at minimum `MyTank.java`). It must be valid Java
that would compile against `robocode.jar`. In your report note per bot: source repo/author, base
class, #files, and any caveat (data-file use, "custom"-token rename you had to do, multi-file, or
anything you had to strip). A reference `MyTank.java` lives at
`scripts/ladder/examples/robots/custom/MyTank.java`.
