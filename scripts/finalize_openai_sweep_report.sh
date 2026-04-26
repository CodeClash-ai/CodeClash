#!/usr/bin/env bash
set -euo pipefail
RUN_ROOT="/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312"
REPORT="$RUN_ROOT/analysis/openai_vs_previous_leaderboard_summary.md"

uv run python - <<'PY'
import json, time
from pathlib import Path
run=Path('/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312')
patterns=[
  'PvpTournament.HuskyBench.r15.s100.p2.gpt-5.gpt-5.4.gpt-5.4-vs-gpt-5.*',
  'PvpTournament.HuskyBench.r15.s100.p2.gpt-5.gpt-5.3-codex.gpt-5.3-codex-vs-gpt-5.*',
]
need={str(i) for i in range(16)}
for _ in range(720):
    done=0
    for pat in patterns:
        ds=sorted(run.glob(pat), key=lambda p:p.stat().st_mtime, reverse=True)
        if not ds: continue
        m=ds[0]/'metadata.json'
        if not m.exists(): continue
        try:j=json.loads(m.read_text())
        except: continue
        rs=set(j.get('round_stats',{}).keys())
        if need.issubset(rs): done+=1
    if done==2:
        print('huskybench complete')
        break
    time.sleep(30)
else:
    raise SystemExit('timeout waiting for huskybench completion')
PY

/Users/muhtasham/Documents/CodeClash/scripts/run_eval_pipeline.sh --log-dir "$RUN_ROOT"

uv run python - <<'PY'
import re
from pathlib import Path
run=Path('/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312')
report=run/'analysis'/'openai_vs_previous_leaderboard_summary.md'
report.parent.mkdir(parents=True, exist_ok=True)
all_tex=run/'analysis'/'elo'/'elo_table_plain.tex'
text=all_tex.read_text() if all_tex.exists() else ''
rows=[]
for line in text.splitlines():
    if '&' in line and '\\\\' in line and 'Model' not in line:
        parts=[p.strip() for p in line.replace('\\\\','').split('&')]
        if len(parts)>=3:
            rows.append(parts)

prev={
'Claude Sonnet 4.5':1385,'GPT-5':1366,'o3':1343,'Claude Sonnet 4':1224,
'GPT-5 Mini':1199,'Gemini 2.5 Pro':1124,'Grok Code Fast':1006,'Qwen3 Coder':952,
}

lines=[]
lines.append('# OpenAI Sweep vs Previous Leaderboard')
lines.append('')
lines.append('Current run root: `/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312`')
lines.append('')
lines.append('## New-model ALL Elo (this run)')
if rows:
    lines.append('| Model | Elo |')
    lines.append('|---|---:|')
    for r in rows:
        model=r[0]
        elo=r[1] if len(r)>1 else ''
        if any(k in model for k in ['gpt-5.4','gpt-5.3-codex','gpt-5']):
            lines.append(f'| {model} | {elo} |')
else:
    lines.append('_Could not parse elo_table_plain.tex_')

lines.append('')
lines.append('## Comparison to previous public leaderboard (ALL Elo)')
lines.append('- Previous top baseline in your provided table: **Claude Sonnet 4.5 = 1385 ± 18**')
lines.append('- Previous **GPT-5 = 1366 ± 17**')
lines.append('')
lines.append('Interpretation guidance: this run uses a much smaller model set (gpt-5, gpt-5.4, gpt-5.3-codex), so Elo scale can shift. Compare directionally, not as strict absolute replacement of global board ranks.')

report.write_text('\n'.join(lines)+'\n')
print(report)
PY
