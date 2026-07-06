"""Figgie replay renderer.

Figgie is a non-spatial trading game, so the "board" is a per-player holdings dashboard.
The engine's ``round_*.json`` records ``initial_hands`` and an ``events`` stream of ``tick``
actions (each player's ask/bid/pass) interleaved with executed ``trade`` events
(``{suit, price, buyer, seller}``). :meth:`parse` replays those to reconstruct each player's
suit holdings and cash at every step; a trade frame highlights the buyer/seller. The goal
suit (secret in-game) is shown since the log reveals it.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

SUITS = ["spades", "hearts", "diamonds", "clubs"]

DRAW_JS = """
const ARENA = (function(){
  const SUITS = ['spades','hearts','diamonds','clubs'];
  const SYM = {spades:'\\u2660', hearts:'\\u2665', diamonds:'\\u2666', clubs:'\\u2663'};
  const SCOL = {spades:'#c9d1d9', hearts:'#e5484d', diamonds:'#f5a623', clubs:'#30a46c'};
  let NP, NAMES, GOAL, COLW;
  function setup(cv, G){
    NP = G.np; NAMES = G.names; GOAL = G.goal; COLW = 150;
    cv.width = NP * COLW + 20; cv.height = 300;
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.fillStyle = '#0d1117'; ctx.fillRect(0,0,cv.width,cv.height);
    for(let p=0;p<NP;p++){
      const x = 10 + p*COLW;
      const isB = f.trade && f.trade.buyer===p, isS = f.trade && f.trade.seller===p;
      ctx.fillStyle = isB ? '#173a26' : isS ? '#3a1a1d' : '#161b22';
      ctx.strokeStyle = isB ? '#30a46c' : isS ? '#e5484d' : '#30363d'; ctx.lineWidth = isB||isS?2:1;
      ctx.beginPath(); ctx.roundRect(x, 10, COLW-12, 270, 8); ctx.fill(); ctx.stroke();
      ctx.textAlign='left'; ctx.textBaseline='alphabetic';
      ctx.fillStyle='#e6edf3'; ctx.font='bold 14px system-ui';
      ctx.fillText(NAMES[p]||('P'+p), x+12, 32);
      ctx.fillStyle='#8b949e'; ctx.font='12px system-ui'; ctx.fillText('$'+f.cash[p], x+12, 50);
      SUITS.forEach((su,si)=>{
        const y = 78 + si*46, n = (f.holdings[p]||{})[su]||0;
        ctx.fillStyle = SCOL[su]; ctx.font='bold 20px system-ui';
        ctx.fillText(SYM[su], x+14, y);
        ctx.fillStyle='#e6edf3'; ctx.font='bold 18px system-ui'; ctx.fillText('\\u00d7 '+n, x+42, y);
        if(su===GOAL){ ctx.strokeStyle='#ffd21f'; ctx.lineWidth=1.5; ctx.strokeRect(x+8, y-20, COLW-28, 30); }
      });
    }
  }
  function side(G, i){
    const f = G.frames[i], SCOL = {spades:'#c9d1d9', hearts:'#e5484d', diamonds:'#f5a623', clubs:'#30a46c'};
    const nm = (p) => (G.names||{})[p] || ('P'+(Number(p)+1));
    let ev;
    if(f.kind==='trade'){
      const t=f.trade;
      ev = `<b style="color:${SCOL[t.suit]}">${nm(t.buyer)}</b> bought ${t.suit} @ $${t.price} from <b>${nm(t.seller)}</b>`;
    } else {
      ev = (f.actions||[]).filter(a=>a.valid&&a.type!=='pass').map(a=>`${nm(a.p)}: ${a.type} ${a.suit||''} ${a.price!=null?('@'+a.price):''}`).join('<br>') || '<span class="muted">(no valid actions)</span>';
    }
    let sc = '';
    if(i===G.frames.length-1 && G.scores){
      sc = '<div class="team"><b>Final scores</b>' + Object.keys(G.scores).map(p=>`<div class="stat"><span>${nm(p)}</span><b>${G.scores[p]>0?'+':''}${G.scores[p]}</b></div>`).join('') + '</div>';
    }
    return `<div class="team"><div class="stat"><span>goal suit</span><b style="color:${SCOL[G.goal]}">${G.goal} \\u2605</b></div>
      <div class="stat"><span>tick</span><b>${f.tick}</b></div></div>
      <div class="team" style="min-height:60px"><b>${f.kind==='trade'?'Trade':'Tick'}</b><div style="margin-top:4px;font-size:13px">${ev}</div></div>${sc}`;
  }
  return {setup, draw, side};
})();
"""


class FiggieReplayer(ReplayRenderer):
    arena = "Figgie"
    sim_glob = "round_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        d = json.loads(raw.decode())
        np_ = d.get("num_players", 4)
        goal = d.get("goal_suit")
        init = d.get("initial_hands", {})
        names = {i: (players[i]["name"] if players and len(players) > i else f"P{i + 1}") for i in range(np_)}
        ante = 50 if np_ == 4 else 40

        holdings = {i: dict(init.get(str(i), {})) for i in range(np_)}
        cash = {i: 350 - ante for i in range(np_)}
        frames = []
        for idx, e in enumerate(d.get("events", [])):
            trade = actions = None
            if e.get("type") == "trade":
                b, s, su, pr = e["buyer"], e["seller"], e["suit"], e["price"]
                holdings[b][su] = holdings[b].get(su, 0) + 1
                holdings[s][su] = holdings[s].get(su, 0) - 1
                cash[b] -= pr
                cash[s] += pr
                trade = {"buyer": b, "seller": s, "suit": su, "price": pr}
            else:
                actions = [
                    {"p": a["player"], "valid": a.get("valid", True), **a.get("action", {})}
                    for a in e.get("actions", [])
                ]
            frames.append(
                {
                    "turn": idx,
                    "tick": e.get("tick"),
                    "kind": e.get("type"),
                    "holdings": {i: dict(holdings[i]) for i in range(np_)},
                    "cash": dict(cash),
                    "trade": trade,
                    "actions": actions,
                }
            )

        scores = {int(k): v for k, v in d.get("scores", {}).items()}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
            winner, draw = None, bool(ranked)
        else:
            winner, draw = names.get(ranked[0][0], f"P{ranked[0][0] + 1}"), False

        return ReplayData(
            w=1,
            h=1,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"names": names, "goal": goal, "scores": scores, "np": np_},
        )
