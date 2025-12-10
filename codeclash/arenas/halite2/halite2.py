from codeclash.arenas.halite.halite import HaliteArena


class Halite2Arena(HaliteArena):
    name: str = "Halite2"
    description: str = """Halite II is a multi-player AI-programming challenge in which bots pilot fleets of spaceships across a continuous space-themed universe.
Players command ships to mine planets for halite, use that resource to build additional ships, and expand control across the map.
Victory depends on efficient resource gathering, fleet management, and strategic expansion to outcompete rival bots for dominance.

You have the choice of writing your Halite bot in one of four programming languages: C++, Haskell, OCaml, or Rust.
Example implementations can be found under the `airesources/` folder.
Your submission should be stored in the `submission/` folder. This folder currently contains an example OCaml bot, but feel free to use any of the supported languages.
Please make sure your main file is named `main.<ext>`, where `<ext>` is the appropriate file extension for your chosen programming language.
You may include additional files as needed, but please ensure:
1. The `submission/` folder contains only files relevant to your bot.
2. The `submission/` folder ONLY contains a single bot (no multiple bots in one submission).
3. Your bot can be compiled. See `runGame.sh` under the corresponding `submission/<language>/` folder to see how we will compile and run your bot.
"""
