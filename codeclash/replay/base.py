"""General replay scaffolding shared by every arena.

The split of responsibilities:

* **base (this module)** owns everything arena-agnostic — the HTML player shell,
  all playback controls, the tournament-info header, the index page, the ascii
  scaffold, sim discovery (incl. `rounds/round_<R>.tar.gz` archives), and file I/O.
* **each arena** (``codeclash/arenas/<arena>/replay.py``) subclasses
  :class:`ReplayRenderer` and owns just two things: ``parse()`` (raw sim bytes ->
  normalized :class:`ReplayData`) and ``DRAW_JS`` (its bespoke canvas + side panel).

The sim on disk can be any format — text (`.jsonl`, `.txt`, `.md`), JSON, or binary.
Discovery hands the arena the raw ``bytes`` and lets it decide how to decode; only the
:class:`ReplayData` it returns is typed and uniform.
"""

from __future__ import annotations

import fnmatch
import json
import re
import tarfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReplayData:
    """Normalized, arena-agnostic playback payload.

    The player shell only relies on ``w``, ``h``, ``frames`` (each frame carrying a
    ``turn``), ``winner`` and ``draw``. Everything an arena's ``DRAW_JS`` additionally
    needs (colors, team names, walls, max health, ...) rides along in ``extra`` and is
    merged into the JS ``G`` object.
    """

    w: int
    h: int
    frames: list[dict]
    winner: str | None = None
    draw: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def payload(self) -> dict:
        """The ``G`` object handed to the JS player."""
        return {"w": self.w, "h": self.h, "frames": self.frames, "winner": self.winner, "draw": self.draw, **self.extra}

    def __bool__(self) -> bool:  # truthy iff it actually has frames to play
        return bool(self.frames)


@dataclass
class GameRef:
    """A single playable game located within a tournament folder.

    Either it lives inside a per-round tar archive (``archive`` + ``member``) or it is a
    loose file on disk (``path``).
    """

    round: int
    sim: int
    archive: Path | None = None
    member: str | None = None
    path: Path | None = None
    group: str = ""  # matchup label, e.g. for a ladder made of many PvP sub-tournaments
    winner: str | None = None  # this game's round winner (from its tournament's metadata)
    sim_winner: str | None = None  # this individual sim's winner (None if unknown/not computed)
    sim_draw: bool = False  # whether this individual sim was a draw


@dataclass
class TournamentInfo:
    """Everything the replay layer needs about a tournament folder."""

    folder: Path
    arena: str
    players: list[dict]  # [{"name": str, "model": str | None}, ...]
    rounds: int | None
    sims_per_round: int | None
    round_winners: dict[int, str]
    games: list[GameRef]


class ReplayRenderer(ABC):
    """Per-arena contract: how to read a sim and how to draw it."""

    arena: str = ""  # must match config.game.name, e.g. "BattleSnake"
    sim_glob: str = "sim_*.jsonl"  # basename glob used to discover sims
    DRAW_JS: str = ""  # defines a global ``ARENA`` object with setup/draw/side
    CSS: str = ""  # optional arena-specific style additions

    @abstractmethod
    def parse(self, raw: bytes, players: list[dict] | None = None) -> ReplayData:
        """Decode raw sim bytes into a :class:`ReplayData`. Input format is opaque."""

    def peek_winner(self, raw: bytes, players: list[dict] | None = None) -> tuple[str | None, bool] | None:
        """Cheaply return ``(winner, draw)`` for a single sim, for the index listing,
        without building all frames. Return ``None`` (the default) if not implemented --
        the index then just omits the per-sim winner rather than paying a full parse."""
        return None


# --------------------------------------------------------------------------------------
# Sim discovery + reading
# --------------------------------------------------------------------------------------


def _sim_index(name: str) -> int:
    """Best-effort sim index from a filename: the last integer in its stem (``sim_18`` -> 18,
    ``round_1`` -> 1), else 0. ``discover_games`` de-duplicates any collisions within a round."""
    nums = re.findall(r"\d+", name.rsplit(".", 1)[0])
    return int(nums[-1]) if nums else 0


def _round_num(name: str) -> int:
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def discover_games(folder: Path, sim_glob: str) -> list[GameRef]:
    """Find every playable game under a tournament folder.

    Handles three layouts: ``rounds/round_<R>.tar.gz`` archives (the common case),
    uncompressed ``rounds/<R>/sim_*`` directories, and a flat folder of sim files
    (e.g. an ad-hoc sample with a single ``sim.json``).
    """
    games: list[GameRef] = []
    rounds_dir = folder / "rounds"
    if rounds_dir.is_dir():
        entries = sorted(rounds_dir.iterdir())
        # Archives first, recording which rounds they cover.
        archived: set[int] = set()
        for entry in entries:
            if entry.is_file() and entry.name.startswith("round") and entry.suffixes[-1:] == [".gz"]:
                rnum = _round_num(entry.name)
                archived.add(rnum)
                with tarfile.open(entry) as tf:
                    for m in tf.getmembers():
                        base = Path(m.name).name
                        if m.isfile() and m.size > 0 and not base.startswith("._") and fnmatch.fnmatch(base, sim_glob):
                            games.append(
                                GameRef(round=rnum, sim=_sim_index(Path(m.name).name), archive=entry, member=m.name)
                            )
        # Then round dirs — but skip any round already sourced from an archive. A round can
        # exist both extracted and tarred; counting both would double up the same games.
        for entry in entries:
            if entry.is_dir() and _round_num(entry.name) not in archived:
                rnum = _round_num(entry.name)
                for f in sorted(entry.iterdir()):
                    if (
                        f.is_file()
                        and f.stat().st_size > 0
                        and not f.name.startswith("._")
                        and fnmatch.fnmatch(f.name, sim_glob)
                    ):
                        games.append(GameRef(round=rnum, sim=_sim_index(f.name), path=f))
    else:
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.stat().st_size > 0 and fnmatch.fnmatch(f.name, sim_glob):
                games.append(GameRef(round=0, sim=_sim_index(f.name), path=f))
    # Ensure sim indices are unique within each round; if a filename scheme collides
    # (or lacks numbers), fall back to enumeration order.
    per_round: dict[int, list[GameRef]] = {}
    for g in games:
        per_round.setdefault(g.round, []).append(g)
    for gs in per_round.values():
        sims = [g.sim for g in gs]
        # Enumerate on collisions, or when the parsed numbers are clearly seeds/timestamps
        # (e.g. Halite's .hlt names) rather than small sim indices.
        if len(set(sims)) != len(sims) or (sims and max(sims) > 4 * len(gs) + 100):
            gs.sort(key=lambda g: g.member or (g.path.name if g.path else ""))
            for i, g in enumerate(gs):
                g.sim = i
    games.sort(key=lambda g: (g.round, g.sim))
    return games


def read_sim(game: GameRef) -> bytes:
    """Read the raw bytes for a game, extracting from its tar archive if needed."""
    if game.archive is not None:
        with tarfile.open(game.archive) as tf:
            f = tf.extractfile(game.member)
            if f is None:
                raise FileNotFoundError(f"{game.member} not found in {game.archive}")
            return f.read()
    return game.path.read_bytes()


# --------------------------------------------------------------------------------------
# Shared HTML player (shell + controls) — arena-agnostic
# --------------------------------------------------------------------------------------

SHELL_CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--dim:#6e7681;--line:#30363d;--panel:#161b22;--btn:#21262d;--btnb:#30363d;--accent:#58a6ff}
:root[data-theme="light"]{--bg:#ffffff;--fg:#1f2328;--muted:#57606a;--dim:#8c959f;--line:#d0d7de;--panel:#f6f8fa;--btn:#f6f8fa;--btnb:#d0d7de;--accent:#0969da}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;margin:0;padding:16px;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
#stage{display:flex;gap:20px;flex-wrap:wrap;align-items:center;justify-content:center}
canvas{background:var(--panel);border-radius:8px}
#panel{min-width:260px}
.row{margin:8px 0}
button{background:var(--btn);color:var(--fg);border:1px solid var(--btnb);border-radius:6px;padding:6px 10px;cursor:pointer;font-size:14px}
button:hover{filter:brightness(1.15)}
#tour{margin-bottom:12px}
.tour-players{font-weight:700;font-size:15px}
.tour-players .pl{white-space:nowrap}
.tour-meta{font-size:12px;margin-top:2px;line-height:1.6}
.tour-meta .k{color:var(--dim)}
.muted{color:var(--muted)}
#back{color:var(--muted);text-decoration:none;font-size:13px;padding:4px 10px;border-radius:6px;transition:color .15s,background .15s}
#back:hover{color:var(--fg);background:var(--panel)}
#winner{font-weight:700;font-size:16px;margin-top:12px}
/* BattleSnake side panel */
.sn{display:flex;align-items:center;gap:8px;margin:6px 0}
.sw{width:14px;height:14px;border-radius:3px}
.hb{height:8px;background:var(--line);border-radius:4px;flex:1;overflow:hidden}
.hf{height:100%}
.dead{opacity:.4;text-decoration:line-through}
/* RobotRumble side panel */
.team{margin:12px 0;padding:10px;background:var(--panel);border-radius:8px}
.tname{display:flex;align-items:center;gap:8px;font-weight:700}
.stat{display:flex;justify-content:space-between;margin:6px 0;font-variant-numeric:tabular-nums}
.team .hb{margin-top:4px}
.tdead{opacity:.45}
"""

SHELL_BODY = """
<div id="stage">
<canvas id="c"></canvas>
<div id="panel">
 <div id="tour"></div>
 <div class="row"><b>Turn <span id="t">0</span></b> / <span id="maxturn">0</span></div>
 <div class="row">
  <button id="first">&#9198;</button><button id="prev">&#9664;</button>
  <button id="play">&#9654; play</button><button id="next">&#9654;</button><button id="last">&#9199;</button>
 </div>
 <div class="row">speed <input id="speed" type="range" min="1" max="30" value="8"></div>
 <input id="scrub" type="range" min="0" max="0" value="0" style="width:100%">
 <div id="side"></div>
 <div id="winner"></div>
</div>
</div>
<a id="back" href="/">&#8592; back to index</a>
"""

# The player state machine. Expects globals ``G`` (ReplayData payload), optional ``TOUR``
# (tournament header), and ``ARENA`` (provided by the arena's DRAW_JS) exposing
# setup(cv, G, ctx) / draw(ctx, cv, G, i) / side(G, i).
PLAYER_JS = """
(function(){
  // Inherit the light/dark choice made on the index (shared via localStorage).
  document.documentElement.setAttribute('data-theme', localStorage.getItem('cc-replay-theme') || 'dark');
  const G = window.G, TOUR = window.TOUR || null, F = G.frames;
  const cv = document.getElementById('c'), ctx = cv.getContext('2d');
  if(!CanvasRenderingContext2D.prototype.roundRect){CanvasRenderingContext2D.prototype.roundRect=function(x,y,w,h,r){this.beginPath();this.moveTo(x+r,y);this.arcTo(x+w,y,x+w,y+h,r);this.arcTo(x+w,y+h,x,y+h,r);this.arcTo(x,y+h,x,y,r);this.arcTo(x,y,x+w,y,r);this.closePath();return this;};}
  ARENA.setup(cv, G, ctx);
  const maxturn = F.length - 1;
  document.getElementById('maxturn').textContent = maxturn;
  document.getElementById('scrub').max = maxturn;
  if(TOUR) document.getElementById('tour').innerHTML = renderTour(TOUR);
  let i = 0, playing = false, timer = null;
  function draw(){
    ARENA.draw(ctx, cv, G, i);
    document.getElementById('t').textContent = F[i].turn;
    document.getElementById('scrub').value = i;
    document.getElementById('side').innerHTML = ARENA.side(G, i);
    document.getElementById('winner').textContent = (i === maxturn) ? ('Winner: ' + (G.draw ? 'TIE' : (G.winner || '\\u2014'))) : '';
  }
  function go(n){ i = Math.max(0, Math.min(maxturn, n)); draw(); }
  function play(){
    playing = !playing;
    document.getElementById('play').innerHTML = playing ? '\\u23f8 pause' : '\\u25b6 play';
    if(playing){ timer = setInterval(()=>{ if(i >= maxturn){ play(); return; } go(i+1); }, 1000 / +document.getElementById('speed').value); }
    else clearInterval(timer);
  }
  document.getElementById('play').onclick = play;
  document.getElementById('next').onclick = ()=>go(i+1);
  document.getElementById('prev').onclick = ()=>go(i-1);
  document.getElementById('first').onclick = ()=>go(0);
  document.getElementById('last').onclick = ()=>go(maxturn);
  document.getElementById('scrub').oninput = (e)=>go(+e.target.value);
  document.getElementById('speed').oninput = ()=>{ if(playing){ play(); play(); } };
  document.addEventListener('keydown', (e)=>{
    if(e.key === 'ArrowRight') go(i+1);
    else if(e.key === 'ArrowLeft') go(i-1);
    else if(e.key === ' '){ e.preventDefault(); play(); }
  });
  function renderTour(t){
    const players = (t.players || []).map(p => `<span class="pl">${p.name}${p.model ? ` <span class="muted">(${p.model})</span>` : ''}</span>`).join(', ');
    const title = t.matchup ? t.matchup : players;
    const line = (k, v) => `<span class="k">${k}</span> ${v}`;
    const rows = [];
    if(t.arena) rows.push(line('arena', `<b>${t.arena}</b>`));
    if(t.matchup && players) rows.push(line('players', players));
    const rd = (t.round != null ? `${t.round}${t.rounds != null ? '/'+t.rounds : ''}` : null);
    if(rd != null) rows.push(line('round', rd) + (t.sim != null ? `  \\u00b7  <span class="k">sim</span> ${t.sim}` : ''));
    if(t.sims != null) rows.push(line('sims/round', t.sims));
    if(t.round_winner) rows.push(line('round winner', `<b>${t.round_winner}</b>`));
    if(t.games != null) rows.push(line('games', t.games));
    if(t.folder) rows.push(`<span class="k">${t.folder}</span>`);
    return `<div class="tour-players">${title}</div><div class="muted tour-meta">${rows.join('<br>')}</div>`;
  }
  draw();
})();
"""


def _script_safe(obj) -> str:
    """JSON for inlining inside a <script> tag (guard against ``</script>``)."""
    return json.dumps(obj).replace("</", "<\\/")


def _doc(head_extra: str, scripts: str) -> str:
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        + head_extra
        + "</head><body>\n"
        + SHELL_BODY
        + "\n"
        + scripts
        + "\n</body></html>\n"
    )


def build_page(data: ReplayData, tour: dict, renderer: ReplayRenderer) -> str:
    """A complete, self-contained replay page (CSS + player + arena JS + data inlined).

    Built on demand by the server and served straight from memory — nothing is written to
    disk.
    """
    head = f"<title>{renderer.arena} replay</title><style>{SHELL_CSS}{renderer.CSS}</style>"
    scripts = (
        "<script>window.G="
        + _script_safe(data.payload)
        + ";window.TOUR="
        + _script_safe(tour)
        + ";</script>\n"
        + "<script>"
        + renderer.DRAW_JS
        + "</script>\n"
        + "<script>"
        + PLAYER_JS
        + "</script>"
    )
    return _doc(head, scripts)


def build_index(tour: TournamentInfo) -> str:
    """Index page: every game with its winner, linking to its replay by game index.

    For a ladder (games carry a ``group`` matchup label) a Matchup column is shown.
    """
    players = ", ".join(p["name"] for p in tour.players) if tour.players else ""
    laddered = any(g.group for g in tour.games)
    rounds = len({g.round for g in tour.games})

    # Show the per-sim winner (if the arena computed it) as well as the round winner,
    # so a decisive individual game isn't mislabeled with its round's aggregate result.
    have_sim_winner = any(g.sim_winner is not None or g.sim_draw for g in tour.games)
    rows = []
    for idx, g in enumerate(tour.games):
        round_winner = g.winner if g.winner is not None else tour.round_winners.get(g.round, "")
        sim_winner = "TIE" if g.sim_draw else (g.sim_winner or "")
        cell = f'<a class="watch" href="game?g={idx}"><span class="tri">&#9654;</span> watch</a>'
        group_td = f"<td>{g.group}</td>" if laddered else ""
        sim_td = f"<td>{sim_winner}</td>" if have_sim_winner else ""
        rows.append(
            f"<tr>{group_td}<td>{g.round}</td><td>{g.sim}</td>{sim_td}<td>{round_winner or ''}</td><td>{cell}</td></tr>"
        )

    style = (
        ":root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--dim:#6e7681;--line:#21262d;"
        "--btn:#21262d;--btnb:#30363d;--accent:#58a6ff}"
        ':root[data-theme="light"]{--bg:#ffffff;--fg:#1f2328;--muted:#57606a;--dim:#8c959f;'
        "--line:#d0d7de;--btn:#f6f8fa;--btnb:#d0d7de;--accent:#0969da}"
        "*{box-sizing:border-box}"
        "body{background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;margin:0;"
        "min-height:100vh;display:flex;flex-direction:column}"
        ".bar{border-bottom:1px solid var(--line)}"
        ".bar-inner{max-width:1000px;margin:0 auto;width:100%;display:flex;align-items:center;"
        "justify-content:space-between;padding:0 24px;height:54px}"
        ".brand{font-weight:700;font-size:16px}"
        "main{flex:1;display:flex;align-items:center;justify-content:center;padding:24px}"
        ".wrap{display:flex;gap:32px;align-items:flex-start;max-width:1000px}"
        ".info{max-width:220px}"
        ".info-title{font-size:16px;font-weight:700;margin-bottom:8px}"
        ".folder{color:var(--dim);font-size:12px;margin-bottom:12px;word-break:break-all}"
        ".meta{color:var(--muted);font-size:13px;line-height:2}"
        ".meta .k{color:var(--dim);display:inline-block;min-width:92px}"
        ".games{overflow-y:auto}table{border-collapse:collapse}"
        "td,th{padding:5px 14px;border-bottom:1px solid var(--line);text-align:left}"
        "th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--bg)}"
        "a{color:var(--accent)}"
        ".btn{background:var(--btn);color:var(--fg);border:1px solid var(--btnb);border-radius:6px;"
        "padding:5px 11px;cursor:pointer;font-size:15px;line-height:1;text-decoration:none}"
        ".btn:hover{filter:brightness(1.15)}"
        ".watch{color:var(--accent);text-decoration:none;font-weight:600;display:inline-flex;align-items:center;gap:6px}"
        ".watch .tri{display:inline-block;font-size:11px;transition:transform .18s ease}"
        ".watch:hover .tri{transform:translateX(4px)}.watch:hover{opacity:.82}"
    )
    kind = "LadderTournament" if laddered else "PvpTournament"
    # Left column: title, folder, then each fact on its own line.
    meta = [f'<div><span class="k">arena</span> {tour.arena}</div>']
    if laddered:
        meta.append(f'<div><span class="k">matchups</span> {len({g.group for g in tour.games})}</div>')
    elif players:
        meta.append(f'<div><span class="k">players</span> {players}</div>')
    meta.append(f'<div><span class="k">rounds</span> {tour.rounds if tour.rounds is not None else rounds}</div>')
    if tour.sims_per_round is not None:
        meta.append(f'<div><span class="k">sims/round</span> {tour.sims_per_round}</div>')
    meta.append(f'<div><span class="k">games</span> {len(tour.games)}</div>')
    info = (
        f"<div class='info'><div class='info-title'>{kind} &middot; {tour.arena}</div>"
        f"<div class='folder'>{tour.folder.name}</div>"
        f"<div class='meta'>{''.join(meta)}</div></div>"
    )
    matchup_th = "<th>matchup</th>" if laddered else ""
    sim_th = "<th>sim winner</th>" if have_sim_winner else ""
    round_th = "<th>round winner</th>" if have_sim_winner else "<th>winner</th>"
    table = (
        f"<div class='games'><table><tr>{matchup_th}<th>round</th><th>sim</th>{sim_th}{round_th}<th></th></tr>"
        + "".join(rows)
        + "</table></div>"
    )
    # Theme toggle (persisted in localStorage) + cap the games table to the info column's height.
    js = (
        "const KEY='cc-replay-theme',root=document.documentElement,btn=document.getElementById('theme');"
        "function apply(t){root.setAttribute('data-theme',t);btn.textContent=(t==='light')?'\\u2600':'\\u263e';}"
        "apply(localStorage.getItem(KEY)||'dark');"
        "btn.onclick=function(){var t=(root.getAttribute('data-theme')==='light')?'dark':'light';"
        "localStorage.setItem(KEY,t);apply(t);};"
        "var iw=document.querySelector('.info'),ig=document.querySelector('.games');"
        "if(iw&&ig)ig.style.maxHeight=iw.offsetHeight+'px';"
    )
    return (
        '<!doctype html><html data-theme="dark"><head><meta charset="utf-8">'
        f"<title>{tour.arena} replays</title><style>{style}</style></head><body>"
        "<header class='bar'><div class='bar-inner'>"
        "<div class='brand'>CodeClash Tournament Replayer</div>"
        "<button id='theme' class='btn' title='Toggle light / dark'></button></div></header>"
        f"<main><div class='wrap'>{info}{table}</div></main>"
        "<script>" + js + "</script></body></html>\n"
    )
