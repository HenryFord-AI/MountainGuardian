#!/usr/bin/env bash
set -euo pipefail
CAP=artifacts/demo_capture
VO=artifacts/demo_voice
OUT=artifacts/final_demo
TMP="$OUT/tmp"
mkdir -p "$TMP"
W=1920; H=1080; FPS=30; TOTAL=136
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
BOLD=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf

still() {
  local img="$1" out="$2" dur="$3" kicker="$4" title="$5" sub="$6"
  local frames
  frames=$(python3 -c "print(round(float('$dur')*30))")
  ffmpeg -y -loglevel error -loop 1 -i "$img" -t "$dur" \
    -vf "scale=1920:1080,zoompan=z='min(zoom+0.00010,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1920x1080:fps=30,drawbox=x=76:y=62:w=1160:h=220:color=0x030e1c@0.82:t=fill,drawbox=x=76:y=62:w=1160:h=220:color=0x4ab0dc@0.34:t=2,drawtext=fontfile=${BOLD}:text='${kicker}':x=110:y=92:fontsize=24:fontcolor=0x45d6ff,drawtext=fontfile=${BOLD}:text='${title}':x=110:y=132:fontsize=52:fontcolor=white,drawtext=fontfile=${FONT}:text='${sub}':x=112:y=214:fontsize=26:fontcolor=0xa5b8cd,format=yuv420p" \
    -an -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p "$out"
}

# Real product remains the visual source. These are editorial labels, not product UI.
still "$CAP/01_overview.png" "$TMP/s0.mp4" 14 "MOUNTAINGUARDIAN" "RISK IS MORE THAN A NUMBER" "Terrain / Glacier / Rainfall / Remote Sensing / History"
still "$CAP/01_overview.png" "$TMP/s1.mp4" 14 "MEET MOUNTAINGUARDIAN" "Multi-Agent Disaster Risk Intelligence" "Evidence-based / Reproducible / Reviewable"
still "$CAP/02_historical_replay.png" "$TMP/s2.mp4" 24 "PROOF I - HISTORICAL REPLAY" "PRE-EVENT ANALYSIS FIRST" "91 / 100 = Baseline Susceptibility | Not event probability"

# The 37-second live segment shows the real Risk Watch scan, including skip/fallback states.
ffmpeg -y -loglevel error -ss 28.5 -t 37 -i "$CAP/poc_full_session.webm" \
  -vf "scale=1920:1080,fps=30,drawbox=x=78:y=58:w=1120:h=96:color=0x030e1c@0.78:t=fill,drawbox=x=78:y=58:w=1120:h=96:color=0x4ab0dc@0.32:t=2,drawtext=fontfile=${BOLD}:text='PROOF II - LIVE RISK WATCH':x=108:y=76:fontsize=29:fontcolor=white,drawtext=fontfile=${FONT}:text='Real scan / explicit missing-data states / deterministic risk engine':x=108:y=116:fontsize=22:fontcolor=0xa5b8cd,format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p "$TMP/s3.mp4"

still "$CAP/07_intelligence_center.png" "$TMP/s4.mp4" 8.5 "TRUST - INTELLIGENCE CENTER" "Every agent can be inspected" "Inputs / Outputs / Runtime / Status"
still "$CAP/08_evidence_center.png" "$TMP/s5.mp4" 8.5 "TRUST - EVIDENCE CENTER" "Every key claim returns to evidence" "Source / Time / Quality / Provenance"
still "$CAP/09_audit_safety.png" "$TMP/s6.mp4" 9 "TRUST - AUDIT & SAFETY" "Critic checks what may be wrong" "Leakage guards / Boundaries / Review"
still "$CAP/10_overview_end.png" "$TMP/s7.mp4" 15.5 "AI WITH EVIDENCE. AI WITH BOUNDARIES." "Evidence -> Agents -> Risk Engine -> Synthesis -> Critic" "Not a disaster probability. Not an official warning."

ffmpeg -y -loglevel error -f lavfi -i color=c=0x05111f:s=1920x1080:r=30:d=5.5 \
  -vf "drawtext=fontfile=${BOLD}:text='MountainGuardian':x=(w-text_w)/2:y=430:fontsize=76:fontcolor=white,drawtext=fontfile=${FONT}:text='Evidence. Intelligence. Review.':x=(w-text_w)/2:y=560:fontsize=30:fontcolor=0x45d6ff,drawtext=fontfile=${FONT}:text='mountainguardian.cn':x=(w-text_w)/2:y=625:fontsize=25:fontcolor=0xa5b8cd,format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p "$TMP/s8.mp4"

: > "$TMP/concat.txt"
for i in {0..8}; do printf "file '%s'\n" "$(realpath "$TMP/s${i}.mp4")" >> "$TMP/concat.txt"; done
ffmpeg -y -loglevel error -f concat -safe 0 -i "$TMP/concat.txt" -c copy "$TMP/visual.mp4"

# Copyright-safe deterministic ambient bed.
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=55:duration=136:sample_rate=48000" \
  -f lavfi -i "sine=frequency=110:duration=136:sample_rate=48000" \
  -filter_complex "[0:a]volume=0.018[a0];[1:a]volume=0.008[a1];[a0][a1]amix=inputs=2:duration=longest:normalize=0,afade=t=in:st=0:d=2.5,afade=t=out:st=133.5:d=2.5[bed]" \
  -map "[bed]" -c:a pcm_s16le "$TMP/ambient.wav"
