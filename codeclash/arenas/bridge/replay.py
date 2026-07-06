"""Bridge replay renderer.

Bridge is a non-spatial card game, so the "board" is a card table rather than a grid. The
engine's ``sim_*.json`` records the full game: the ``bids`` auction, the final ``contract``,
every trick in ``played_tricks`` (each a list of ``{position, card}`` in play order), and
``tricks_won`` / scores. :meth:`parse` expands that into one frame per action (each bid,
then each card played), computing the running trick winner (highest trump, else highest of
the led suit) since the log only stores the final tally.

Seats: 0=N, 1=E, 2=S, 3=W; teams N/S vs E/W.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

SEATS = ["N", "E", "S", "W"]
TEAM = {0: "NS", 1: "EW", 2: "NS", 3: "EW"}
RANK_ORDER = "23456789TJQKA"

DRAW_JS = """
const ARENA = (function(){
  const SUIT = {S:'\\u2660', H:'\\u2665', D:'\\u2666', C:'\\u2663'};
  const RED = {H:1, D:1};
  let NAMES;
  // seat -> [x,y] anchor for that seat's played card (N top, E right, S bottom, W left)
  const POS = {0:[280,150], 1:[400,280], 2:[280,410], 3:[160,280]};
  const LABEL = {0:[280,60], 1:[500,280], 2:[280,520], 3:[60,280]};
  function setup(cv, G){ NAMES = G.names || {}; cv.width = 560; cv.height = 560; }
  function card(ctx, cx, cy, c){
    ctx.fillStyle = '#f5f5f0'; ctx.strokeStyle = '#111'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(cx-22, cy-30, 44, 60, 5); ctx.fill(); ctx.stroke();
    ctx.fillStyle = RED[c[1]] ? '#d61f2b' : '#111';
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.font='bold 18px system-ui';
    ctx.fillText((c[0]==='T'?'10':c[0]) + SUIT[c[1]], cx, cy);
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.fillStyle = '#0d1117'; ctx.fillRect(0,0,cv.width,cv.height);
    ctx.beginPath(); ctx.arc(280,280,170,0,7); ctx.fillStyle='#143d2b'; ctx.fill();
    ctx.strokeStyle='#2d6a4f'; ctx.lineWidth=2; ctx.stroke();
    // seat labels + team trick counts
    ctx.textAlign='center'; ctx.textBaseline='middle';
    for(let s=0;s<4;s++){
      const [lx,ly] = LABEL[s];
      ctx.fillStyle = (f.winner===s) ? '#ffd21f' : '#e6edf3';
      ctx.font = 'bold 13px system-ui';
      ctx.fillText(`${SEATS[s]} \\u00b7 ${NAMES[s]||''}`, lx, ly);
    }
    // contract in the center (once the auction has set it)
    ctx.fillStyle='#8b949e'; ctx.font='13px system-ui';
    if(f.contract){
      const c=f.contract, sy=(c.suit==='NT')?'NT':SUIT[c.suit]||c.suit;
      ctx.fillStyle = RED[c.suit] ? '#ff7b82' : '#e6edf3'; ctx.font='bold 20px system-ui';
      ctx.fillText(`${c.level}${sy}${c.doubled?' X':''} by ${SEATS[c.declarer]}`, 280, 268);
      ctx.fillStyle='#8b949e'; ctx.font='12px system-ui';
      ctx.fillText(`trick ${f.trickNum}  \\u00b7  NS ${f.won.NS} \\u2013 EW ${f.won.EW}`, 280, 296);
    } else {
      ctx.fillStyle='#8b949e'; ctx.font='14px system-ui'; ctx.fillText('auction', 280, 280);
    }
    // current trick cards
    for(const pos in f.trick){ const [cx,cy]=POS[pos]; card(ctx, cx, cy, f.trick[pos]); }
  }
  function side(G, i){
    const f = G.frames[i];
    // auction grid: columns N E S W, one bid per cell in dealing order
    let rows = '', cells = f.bids.map(b=>b);
    const head = SEATS.map(s=>`<th style="padding:2px 8px">${s}</th>`).join('');
    // pad so the first bid sits under its seat column
    const first = f.bids.length ? f.bids[0].position : 0;
    let line = '<tr>' + '<td></td>'.repeat(first);
    let col = first;
    for(const b of f.bids){
      const red = (b.bid.includes('H')||b.bid.includes('D')) ? 'color:#ff7b82' : '';
      line += `<td style="padding:2px 8px;${red}">${b.bid}</td>`;
      col++; if(col===4){ rows += line+'</tr>'; line='<tr>'; col=0; }
    }
    if(line!=='<tr>') rows += line+'</tr>';
    return `<div class="team"><b>Auction</b>
      <table style="border-collapse:collapse;font-size:13px;margin-top:4px"><tr>${head}</tr>${rows}</table></div>
      <div class="stat"><span>phase</span><b>${f.phase==='bid'?'bidding':'play'}</b></div>
      <div class="stat"><span>tricks</span><b>NS ${f.won.NS} \\u2013 EW ${f.won.EW}</b></div>`;
  }
  return {setup, draw, side};
})();
"""


def _rank(card: str) -> int:
    return RANK_ORDER.index(card[0])


def _trick_winner(trick: list[dict], trump: str | None) -> int:
    led = trick[0]["card"][1]
    best_pos, best_key = None, None
    for play in trick:
        suit = play["card"][1]
        tier = 2 if (trump and suit == trump) else (1 if suit == led else 0)
        key = (tier, _rank(play["card"]))
        if best_key is None or key > best_key:
            best_key, best_pos = key, play["position"]
    return best_pos


class BridgeReplayer(ReplayRenderer):
    arena = "Bridge"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        d = json.loads(raw.decode())
        bids = d.get("bids", [])
        contract = d.get("contract")
        played = d.get("played_tricks", [])
        names = {i: (players[i]["name"] if players and len(players) > i else SEATS[i]) for i in range(4)}

        frames = []
        acc = []
        for b in bids:
            acc = acc + [b]
            frames.append(
                {
                    "turn": len(frames),
                    "phase": "bid",
                    "bids": list(acc),
                    "contract": None,
                    "trick": {},
                    "trickNum": 0,
                    "won": {"NS": 0, "EW": 0},
                    "winner": None,
                }
            )

        trump = contract["suit"] if contract and contract.get("suit") in ("S", "H", "D", "C") else None
        won = {"NS": 0, "EW": 0}
        for tnum, trick in enumerate(played, start=1):
            cur = {}
            for play in trick:
                cur[play["position"]] = play["card"]
                frames.append(
                    {
                        "turn": len(frames),
                        "phase": "play",
                        "bids": list(acc),
                        "contract": contract,
                        "trick": dict(cur),
                        "trickNum": tnum,
                        "won": dict(won),
                        "winner": None,
                    }
                )
            w = _trick_winner(trick, trump)
            won[TEAM[w]] += 1
            frames[-1]["winner"] = w
            frames[-1]["won"] = dict(won)

        score = d.get("normalized_score", {})
        ns, ew = score.get("NS", 0), score.get("EW", 0)
        if ns > ew:
            winner, draw = f"{names[0]}/{names[2]} (NS)", False
        elif ew > ns:
            winner, draw = f"{names[1]}/{names[3]} (EW)", False
        else:
            winner, draw = None, True

        return ReplayData(w=1, h=1, frames=frames, winner=winner, draw=draw, extra={"names": names})
