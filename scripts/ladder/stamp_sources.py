"""Stamp source provenance onto every RoboCode port and emit scripts/ladder/SOURCES.md.

Each bot was imported (copy-in) from an open-source classic-Robocode repo. This records where,
in two consistent places: (1) a header comment prepended to every ports/<slug>/*.java so the
attribution travels with the bot onto its human/* branch; (2) a committed SOURCES.md table.
Source blob URLs use /blob/HEAD/ (resolves to each repo's default branch).
"""

import json
from pathlib import Path

PORTS = Path(__file__).parent / "ports"

# repo -> (author, license)
REPO_META = {
    "robo-code/robocode": ("Robocode (Mathew Nelson / Flemming N. Larsen et al.)", "EPL-1.0"),
    "PEZ/Bots": ("PEZ (Peter Strömberg) et al.", "RWPCL"),
    "AdmiralRasmussen/robocode": ("collected classic bots (see repo)", "unspecified"),
    "namnguyenthanhwork/RoboCode-GuessFactor-MeleeStrategy": ("namnguyenthanhwork", "unspecified"),
    "philipmjohnson/robocode-pmj-dacruzer": ("Philip Johnson", "unspecified"),
    "mgalushka/robocode-robots": ("Maxim Galushka / CrazyBassoonist et al.", "unspecified"),
    "gjgomez/RoboCodeSample": ("gjgomez", "unspecified"),
    "johan-adriaans/BerendBotje": ("Johan Adriaans", "unspecified"),
    "winstliu/robocode": ("winstliu", "unspecified"),
    "pranav-prakash/TheCarverBot": ("Pranav Prakash", "unspecified"),
    "JonHarder/RoboCodeCompetition": ("JonHarder", "unspecified"),
    "g-otn/robocode-reimu": ("g-otn", "unspecified"),
    "TannerRogalsky/Robocode": ("Tanner Rogalsky", "unspecified"),
    "txeverson/robocode": ("txeverson", "unspecified"),
    "Tibola/robocode": ("Tibola", "unspecified"),
    "kylebennett/Robocode": ("Kyle Bennett", "unspecified"),
    "linuxuser0/genetic": ("linuxuser0", "unspecified"),
    "josephjeon/RoboCode": ("Joseph Jeon", "unspecified"),
    "zcjerry229/RoboCode": ("zcjerry229", "unspecified"),
    "alpian/robocode": ("alpian", "unspecified"),
    "kcanida/robocode-kkc-pikachu": ("kcanida", "unspecified"),
    "it-economics/robocode": ("it-economics", "unspecified"),
}

S = "robocode.samples/src/main/java/sample/"
SEX = "robocode.samples/src/main/java/sampleex/"
# slug -> (repo, primary source path)
SRC = {
    # robo-code samples (EPL)
    "sittingduck": ("robo-code/robocode", S+"SittingDuck.java"), "walls": ("robo-code/robocode", S+"Walls.java"),
    "corners": ("robo-code/robocode", S+"Corners.java"), "ramfire": ("robo-code/robocode", S+"RamFire.java"),
    "crazy": ("robo-code/robocode", S+"Crazy.java"), "spinbot": ("robo-code/robocode", S+"SpinBot.java"),
    "tracker": ("robo-code/robocode", S+"Tracker.java"), "trackfire": ("robo-code/robocode", S+"TrackFire.java"),
    "fire": ("robo-code/robocode", S+"Fire.java"), "myfirstrobot": ("robo-code/robocode", S+"MyFirstRobot.java"),
    "velocirobot": ("robo-code/robocode", S+"VelociRobot.java"),
    "regullarmonk": ("robo-code/robocode", SEX+"ProxyOfGreyEminence.java"),
    # PEZ/Bots (RWPCL)
    "aristocles": ("PEZ/Bots", "pez/micro/Aristocles.java"), "blackwidow": ("PEZ/Bots", "pez/micro/BlackWidow.java"),
    "pugilist": ("PEZ/Bots", "pez/mini/Pugilist.java"), "gouldingi": ("PEZ/Bots", "pez/mini/Gouldingi.java"),
    "leach": ("PEZ/Bots", "pez/mini/Leach.java"), "icarus": ("PEZ/Bots", "pez/nano/Icarus.java"),
    "littlebrother": ("PEZ/Bots", "pez/nano/LittleBrother.java"), "tityus": ("PEZ/Bots", "pez/mini/Tityus.java"),
    "frankie": ("PEZ/Bots", "pez/frankie/Frankie.java"), "mako": ("PEZ/Bots", "pez/mako/Mako.java"),
    "chironex_micro": ("PEZ/Bots", "pez/micro/ChironexFleckeri.java"), "vertimicro": ("PEZ/Bots", "pez/micro/VertiMicro.java"),
    "chironex_mini": ("PEZ/Bots", "pez/mini/ChironexFleckeri.java"), "hypoleach": ("PEZ/Bots", "pez/mini/HypoLeach.java"),
    "paolo": ("PEZ/Bots", "pez/mini/Paolo.java"), "vertileach": ("PEZ/Bots", "pez/mini/VertiLeach.java"),
    "littleevilbrother": ("PEZ/Bots", "pez/nano/LittleEvilBrother.java"), "poet": ("PEZ/Bots", "pez/femto/Poet.java"),
    "wallspoet": ("PEZ/Bots", "pez/femto/WallsPoet.java"), "haikuwalls": ("PEZ/Bots", "pez/femto/HaikuWalls.java"),
    "droidpoet": ("PEZ/Bots", "pez/femto/DroidPoet.java"), "gf1": ("PEZ/Bots", "pez/etc/GF1.java"),
    "leachpmc": ("PEZ/Bots", "pez/etc/LeachPMC.java"), "swiffer": ("PEZ/Bots", "pez/clean/Swiffer.java"),
    "smallpoet": ("PEZ/Bots", "pez/femto/SmallPoet.java"), "haikupoet": ("PEZ/Bots", "pez/femto/HaikuPoet.java"),
    "blackwidow_mini": ("PEZ/Bots", "pez/mini/BlackWidow.java"), "wallspoetas": ("PEZ/Bots", "pez/femto/WallsPoetAS.java"),
    "wallspoethaiku": ("PEZ/Bots", "pez/femto/WallsPoetHaiku.java"), "marshmallow": ("PEZ/Bots", "pez/Marshmallow.java"),
    # AdmiralRasmussen bot-collection
    "drussgt": ("AdmiralRasmussen/robocode", "bot-collection/DrussGT.java"),
    "hawkonfire": ("AdmiralRasmussen/robocode", "bot-collection/HawkOnFireOS.java"),
    "wavesurfing": ("AdmiralRasmussen/robocode", "bot-collection/WaveSurfing.java"),
    # others
    "cham": ("namnguyenthanhwork/RoboCode-GuessFactor-MeleeStrategy", "Cham.java"),
    "dacruzer": ("philipmjohnson/robocode-pmj-dacruzer", "src/main/java/pmj/DaCruzer.java"),
    "supermercutio": ("mgalushka/robocode-robots", "src/main/java/sample/SuperMercutio.java"),
    "supercrazy": ("mgalushka/robocode-robots", "src/main/java/sample/SuperCrazy.java"),
    "superwalls": ("mgalushka/robocode-robots", "src/main/java/sample/SuperWalls.java"),
    "supertracker": ("mgalushka/robocode-robots", "src/main/java/sample/SuperTracker.java"),
    "superspinbot": ("mgalushka/robocode-robots", "src/main/java/sample/SuperSpinBot.java"),
    "supercorners": ("mgalushka/robocode-robots", "src/main/java/sample/SuperCorners.java"),
    "superramfire": ("mgalushka/robocode-robots", "src/main/java/sample/SuperRamFire.java"),
    "maximbot": ("mgalushka/robocode-robots", "src/main/java/com/maximgalushka/robocode/MaximBot.java"),
    "mb2": ("gjgomez/RoboCodeSample", "Mb2.java"),
    "berendbotje": ("johan-adriaans/BerendBotje", "src/hackersNL/BerendBotje.java"),
    "thecarver": ("pranav-prakash/TheCarverBot", "pt/TheCarver.java"),
    "bobthebuilder": ("winstliu/robocode", "exam2016/BobTheBuilder.java"),
    "starterbot": ("JonHarder/RoboCodeCompetition", "src/starterbot/StarterBot.java"),
    "reimu": ("g-otn/robocode-reimu", "src/Alpha/Reimu.java"),
    "tannerbot1": ("TannerRogalsky/Robocode", "Tannerbot1.java"),
    "crawler": ("txeverson/robocode", "Crawler.java"),
    "markiv": ("Tibola/robocode", "miv/MarkIV.java"),
    "hugbot": ("kylebennett/Robocode", "BasicRobots/kylebennett/HugBot.java"),
    "gruffalo": ("kylebennett/Robocode", "BasicRobots/kylebennett/TheGruffalo.java"),
    "genetic": ("linuxuser0/genetic", "Genetic.java"),
    "gntest": ("josephjeon/RoboCode", "GNtest.java"),
    "markrobo": ("zcjerry229/RoboCode", "src/MarkRobo/MarkRobo.java"),
    "ianstank": ("alpian/robocode", "src/main/java/com/github/alpian/robocode/tanks/IansTank.java"),
    "tarektank": ("alpian/robocode", "src/main/java/com/github/alpian/robocode/tanks/TarekTank.java"),
    "pikachu": ("kcanida/robocode-kkc-pikachu", "src/main/java/kkc/Pikachu.java"),
    "ite_bomax": ("it-economics/robocode", "src/main/java/com/ite/robocode/BomaxBot.java"),
    "ite_claptrap": ("it-economics/robocode", "src/main/java/com/ite/robocode/ClapTrap.java"),
    "ite_cliffbot2": ("it-economics/robocode", "src/main/java/com/ite/robocode/CliffBot2.java"),
    "ite_ctbot": ("it-economics/robocode", "src/main/java/com/ite/robocode/CtBot.java"),
    "ite_florian2": ("it-economics/robocode", "src/main/java/com/ite/robocode/Florian2Bot.java"),
    "ite_m9": ("it-economics/robocode", "src/main/java/com/ite/robocode/MMMMMMMMM.java"),
    "ite_simple": ("it-economics/robocode", "src/main/java/com/ite/robocode/SimpleBot.java"),
    "ite_terminator": ("it-economics/robocode", "src/main/java/com/ite/robocode/Terminator.java"),
}

# --- Wave-2 discovery imports (34 more repos) -------------------------------------------------
for _r in ["TRex22/DeepThought", "zhiwei121/robocode-hero", "muzardo/robocode-trianglehunter",
           "joaocarpim/robocode_CPS", "gabriel-lw/QuadWall_robocode", "avsthiago/SadBot-Robocode",
           "John-Paul-R/Vergere", "Luke-F-W/NagiSphere-Games-Fleadh-2026", "andrekorol/my-robocode-robots",
           "mcd8604/robocode", "LoganCSC/robocode-robots", "sacdalance/robrrrat", "rafaeljdesa/robocode",
           "dankraemer/robocode", "iagomonteiro13579/robocode.NPC", "vikdov/RoboCodeEvent",
           "denssle/Robocode", "lucasgch/titan", "kinnla/misc", "pmontp19/robocode",
           "MiradoConsulting/roleksii", "barriosnahuel/algorithms-robocode-kenchu", "Team488/RobocodeRobots",
           "joaomcarvalho/robocode", "WouterJoosse/Robocode", "looklazy/robocode",
           "TechnischeInformatica/Robocode2013", "Alexbay218/Robocode-612", "pseminatore/jnk",
           "vftheodoro/BarbieScript-RoboCode", "alexjamesmacpherson/robocode", "andr3eee1/Robocode-Nerdvana",
           "UR4N0-235/UR4NO", "0x65-e/Kokomo"]:
    REPO_META[_r] = (_r.split("/")[0], "unspecified")

SRC.update({
    "deepthought": ("TRex22/DeepThought", "src/DeepThought.java"),
    "hero_pm": ("zhiwei121/robocode-hero", "Hero.java"),
    "trianglehunter": ("muzardo/robocode-trianglehunter", "Main.java"),
    "wrecker": ("joaocarpim/robocode_CPS", "Wrecker.java"),
    "quadwall": ("gabriel-lw/QuadWall_robocode", "quadwall/QuadWall.java"),
    "sadbot": ("avsthiago/SadBot-Robocode", "aps_robocode/SadBot.java"),
    "vergere": ("John-Paul-R/Vergere", "origin/nano/Vergere.java"),
    "nagisphere": ("Luke-F-W/NagiSphere-Games-Fleadh-2026", "Nagisphere.java"),
    "myfirstkiller": ("andrekorol/my-robocode-robots", "src/andykbr/MyFirstKiller.java"),
    "exterminador": ("andrekorol/my-robocode-robots", "src/univap/ExterminadorPrimeiroGrau.java"),
    "oppswantmedead": ("andrekorol/my-robocode-robots", "src/againstallodds/OppsWantMeDead.java"),
    "hunter": ("mcd8604/robocode", "src/mcd/Hunter.java"),
    "dodgebot2": ("LoganCSC/robocode-robots", "src/com/barrybecker4/DodgeBot2.java"),
    "robrrrat": ("sacdalance/robrrrat", "RobrrRat.java"),
    "ultron": ("rafaeljdesa/robocode", "Ultron.java"),
    "juggernaut": ("dankraemer/robocode", "Juggernaut.java"),
    "npcsniper": ("iagomonteiro13579/robocode.NPC", "npc/NPCSniperBot.java"),
    "dominatorx": ("vikdov/RoboCodeEvent", "DominatorX.java"),
    "megaborsten": ("denssle/Robocode", "MegaBorsten2000.java"),
    "bt7274": ("lucasgch/titan", "BT_7274_V6.6.java"),
    "antiwalls": ("kinnla/misc", "robocode/AntiWalls.java"),
    "propiavancat": ("pmontp19/robocode", "src/robots/PropiAvancat.java"),
    "roleksii": ("MiradoConsulting/roleksii", "src/main/java/ROLEKSII.java"),
    "tirolio": ("barriosnahuel/algorithms-robocode-kenchu", "src/main/java/pnt/TiroLioYCoshaGolda3.java"),
    "meow": ("Team488/RobocodeRobots", "Robots/src/YYK/Meow.java"),
    "jeujdapeu": ("joaomcarvalho/robocode", "robots/jeuj/JeujDaPeu.java"),
    "infinitylock": ("WouterJoosse/Robocode", "src/wiki/InfinityLock.java"),
    "chilibot": ("looklazy/robocode", "src/chili/ChiliBot.java"),
    "tearsofsteel": ("TechnischeInformatica/Robocode2013", "src/TearsofSteel.java"),
    "shreker": ("Alexbay218/Robocode-612", "robots/Alexbay218/Shreker.java"),
    "dodgebot_jnk": ("pseminatore/jnk", "Dodge_Bot.java"),
    "barbiescript": ("vftheodoro/BarbieScript-RoboCode", "Source Code BarbieScript/BarbieScript.java"),
    "wilde": ("alexjamesmacpherson/robocode", "Wilde.java"),
    "npcomplete": ("andr3eee1/Robocode-Nerdvana", "src/npcompute/NPcomplete.java"),
    "ur4no": ("UR4N0-235/UR4NO", "UR4NO.java"),
    "kokomo": ("0x65-e/Kokomo", "src/california/surf/Kokomo.java"),
})

HDR_TAG = "// CodeClash ladder import"


def url(repo, path):
    return f"https://github.com/{repo}/blob/HEAD/{path}"


def header(slug):
    repo, path = SRC[slug]
    author, lic = REPO_META[repo]
    return (
        f"{HDR_TAG}\n"
        f"// Source: {url(repo, path)}\n"
        f"// Author: {author}   License: {lic}\n"
        f"// Imported verbatim; only repackaged to the arena package + main class renamed to MyTank"
        + (" (+ helper files flattened)." if len(list((PORTS/slug).glob('*.java'))) > 1 else ".")
        + "\n"
    )


def strip_header(text):
    """Remove a previously-stamped CodeClash header block (contiguous leading // lines)."""
    lines = text.splitlines(keepends=True)
    if not lines or HDR_TAG not in (lines[0] if lines else ""):
        return text
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("//"):
        i += 1
    return "".join(lines[i:])


def main():
    slugs = sorted(d.name for d in PORTS.iterdir() if d.is_dir() and not d.name.startswith("_"))
    missing = [s for s in slugs if s not in SRC]
    if missing:
        print("WARNING: no source mapping for:", missing)
    stamped = 0
    for slug in slugs:
        if slug not in SRC:
            continue
        h = header(slug)
        for j in sorted((PORTS / slug).glob("*.java")):
            t = strip_header(j.read_text())  # idempotent: drop any prior header, re-stamp
            j.write_text(h + t)
            stamped += 1
    # SOURCES.md
    rows = []
    for slug in slugs:
        if slug not in SRC:
            continue
        repo, path = SRC[slug]
        author, lic = REPO_META[repo]
        nf = len(list((PORTS / slug).glob("*.java")))
        rows.append(f"| `{slug}` | [{repo}]({url(repo, path)}) | {author} | {lic} | {nf} |")
    md = (
        "# RoboCode ladder — bot sources\n\n"
        "Every `human/robocode/<slug>` bot on `CodeClash-ai/RoboCode` was imported (copy-in) from an\n"
        "open-source **classic Robocode** repo below — imported verbatim, only repackaged to\n"
        "`package custom;` and the main class renamed to `MyTank` (helper files flattened where needed).\n"
        "Each port file also carries this provenance as a header comment. URLs use `/blob/HEAD/`.\n\n"
        "| slug | source | author | license | files |\n|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n\n"
        "Licenses marked *unspecified* had no explicit LICENSE in the source repo; classic RoboWiki\n"
        "bots are conventionally under the RWPCL. Verify before any redistribution beyond research use.\n"
    )
    (Path(__file__).parent / "SOURCES.md").write_text(md)
    print(f"Stamped {stamped} files across {len([s for s in slugs if s in SRC])} bots; wrote SOURCES.md ({len(rows)} rows).")


if __name__ == "__main__":
    main()
