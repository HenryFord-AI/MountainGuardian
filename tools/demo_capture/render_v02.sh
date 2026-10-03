#!/usr/bin/env bash
set -euo pipefail

CAP=artifacts/demo_capture
OUT=artifacts/final_demo_v02
VO="$OUT/voice"
TMP="$OUT/tmp"
mkdir -p "$VO" "$TMP"
W=1920; H=1080; FPS=30; TOTAL=136
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
BOLD=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc

# Public-domain CCTV footage of the 2026-08-26 Gyirong Port mudslide.
INTRO_URL='https://upload.wikimedia.org/wikipedia/commons/9/9a/Mudslide_at_Gyirong_Port_1.webm'
curl -L --fail --retry 3 "$INTRO_URL" -o "$TMP/gyirong_mudslide.webm"

# Standard Mandarin female narration. Microsoft Chinese neural voice via edge-tts.
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text '在高山峡谷里，风险从来不只是一个数字。地形、冰川、降水、遥感和历史灾害，会共同改变风险。' --write-media "$VO/vo1.mp3"
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text '这就是 MountainGuardian，山河守望者。它让不同专业的 AI 像一个受约束的研究团队一样，基于证据协同分析。' --write-media "$VO/vo2.mp3"
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text '先看一次真实灾害。系统只读取灾前可获得的证据。不同 Agent 独立分析地形、冰冻圈、气象和遥感。系统得到九十一分的基线易感性指数。它不是百分之九十一的发生概率。结果先冻结，之后才打开灾后证据验证。' --write-media "$VO/vo3.mp3"
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text 'Risk Watch 会获取当前环境数据，完成标准化和质量检查。数据缺失或模型不可用时，系统会明确标记跳过或回退。风险指数由确定性模型计算，不由大模型自由生成。Synthesizer 负责综合，Critic 再检查证据、过度推断和科学边界。' --write-media "$VO/vo4.mp3"
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text 'AI 给出结果，并不意味着我们就应该直接相信它。在 Intelligence Center 中，每个 Agent 的输入、输出和状态都可以检查。关键结论可以追溯到证据、来源、时间和数据质量。Critic 还会主动寻找：这个结论为什么可能不成立。' --write-media "$VO/vo5.mp3"
edge-tts --voice zh-CN-XiaoxiaoNeural --rate=-4% --text 'MountainGuardian 不让大模型直接预测灾害。它让 AI 基于证据分析，用可复现模型计算风险，再复核结论和边界。让 AI 知道答案从哪里来，也知道自己不能说什么。' --write-media "$VO/vo6.mp3"

# Film-style opening title. No persistent editorial overlay.
ffmpeg -y -loglevel error -f lavfi -i color=c=0x02070d:s=1920x1080:r=30:d=4 \
  -vf "drawtext=fontfile=${BOLD}:text='山河守望者':x=(w-text_w)/2:y=430:fontsize=86:fontcolor=white:alpha='if(lt(t,1.2),t/1.2,if(lt(t,3.2),1,(4-t)/0.8))',drawtext=fontfile=${FONT}:text='MOUNTAINGUARDIAN':x=(w-text_w)/2:y=550:fontsize=28:fontcolor=0x8fcde8:alpha='if(lt(t,1.5),t/1.5,if(lt(t,3.2),1,(4-t)/0.8))',format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 19 "$TMP/s0.mp4"

# 7-second real disaster opening; stabilize editorial treatment by using a fixed crop only.
ffmpeg -y -loglevel error -ss 0 -t 7 -i "$TMP/gyirong_mudslide.webm" \
  -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,eq=brightness=-0.05:contrast=1.06:saturation=0.82,vignette=PI/7,fade=t=in:st=0:d=0.45,fade=t=out:st=6.25:d=0.75,format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 20 "$TMP/s1.mp4"

stable_still() {
  local img="$1" out="$2" dur="$3"
  ffmpeg -y -loglevel error -loop 1 -i "$img" -t "$dur" \
    -vf "scale=1920:1080,fade=t=in:st=0:d=0.28,fade=t=out:st=$(python3 - <<PY
print(max(0,float('$dur')-0.35))
PY
):d=0.35,format=yuv420p" \
    -an -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p "$out"
}

# Stable product shots: no zoompan, no drift, no floating English box.
stable_still "$CAP/01_overview.png" "$TMP/s2.mp4" 11
stable_still "$CAP/02_historical_replay.png" "$TMP/s3.mp4" 24

# Real Risk Watch scan recording. Keep the UI itself as the protagonist.
ffmpeg -y -loglevel error -ss 28.5 -t 36 -i "$CAP/poc_full_session.webm" \
  -vf "scale=1920:1080,fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st=35.5:d=0.5,format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$TMP/s4.mp4"

stable_still "$CAP/07_intelligence_center.png" "$TMP/s5.mp4" 8
stable_still "$CAP/08_evidence_center.png" "$TMP/s6.mp4" 8
stable_still "$CAP/09_audit_safety.png" "$TMP/s7.mp4" 8
stable_still "$CAP/10_overview_end.png" "$TMP/s8.mp4" 22

# Film-style closing title, mirroring the opening.
ffmpeg -y -loglevel error -f lavfi -i color=c=0x02070d:s=1920x1080:r=30:d=8 \
  -vf "drawtext=fontfile=${BOLD}:text='山河守望者':x=(w-text_w)/2:y=390:fontsize=82:fontcolor=white:alpha='if(lt(t,1.5),t/1.5,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='MOUNTAINGUARDIAN':x=(w-text_w)/2:y=500:fontsize=27:fontcolor=0x8fcde8:alpha='if(lt(t,1.8),t/1.8,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='Evidence. Intelligence. Review.':x=(w-text_w)/2:y=590:fontsize=27:fontcolor=0x45d6ff:alpha='if(lt(t,2.2),t/2.2,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='mountainguardian.cn':x=(w-text_w)/2:y=650:fontsize=24:fontcolor=0x9cafc1:alpha='if(lt(t,2.4),t/2.4,if(lt(t,6.8),1,(8-t)/1.2))',format=yuv420p" \
  -an -c:v libx264 -preset veryfast -crf 19 "$TMP/s9.mp4"

: > "$TMP/concat.txt"
for i in {0..9}; do printf "file '%s'\n" "$(realpath "$TMP/s${i}.mp4")" >> "$TMP/concat.txt"; done
ffmpeg -y -loglevel error -f concat -safe 0 -i "$TMP/concat.txt" -c copy "$TMP/visual.mp4"

# Subtle copyright-safe ambient bed: low drone + filtered pink noise; stronger only in the opening.
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=48:duration=136:sample_rate=48000" \
  -f lavfi -i "sine=frequency=72:duration=136:sample_rate=48000" \
  -f lavfi -i "anoisesrc=color=pink:duration=136:sample_rate=48000" \
  -filter_complex "[0:a]volume=0.010[a0];[1:a]volume=0.004[a1];[2:a]lowpass=f=900,highpass=f=70,volume=0.010[a2];[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0,afade=t=in:st=0:d=2,afade=t=out:st=133:d=3[bed]" \
  -map "[bed]" -c:a pcm_s16le "$TMP/ambient.wav"

# Chinese subtitles aligned to the stable v0.2 structure.
python3 - "$OUT/subtitles.srt" <<'PY'
import sys
from pathlib import Path
c=[
(4.6,10.8,'在高山峡谷里，风险从来不只是一个数字。'),
(10.8,17.2,'地形、冰川、降水、遥感和历史灾害，会共同改变风险。'),
(17.2,22.0,'这就是 MountainGuardian，山河守望者。'),
(22.0,28.8,'它让不同专业的 AI 像一个受约束的研究团队一样，基于证据协同分析。'),
(29.5,35.0,'先看一次真实灾害。系统只读取灾前可获得的证据。'),
(35.0,41.0,'不同 Agent 独立分析地形、冰冻圈、气象和遥感。'),
(41.0,47.0,'系统得到 91 分的基线易感性指数。它不是 91% 的发生概率。'),
(47.0,52.0,'结果先冻结，之后才打开灾后证据验证。'),
(53.0,61.0,'Risk Watch 获取当前环境数据，完成标准化和质量检查。'),
(61.0,69.5,'数据缺失或模型不可用时，系统会明确标记跳过或回退。'),
(69.5,77.0,'风险指数由确定性模型计算，不由大模型自由生成。'),
(77.0,85.0,'Synthesizer 负责综合，Critic 再检查证据、过度推断和科学边界。'),
(85.5,92.5,'AI 给出结果，并不意味着我们就应该直接相信它。'),
(92.5,101.0,'每个 Agent 的输入、输出和状态都可以检查。'),
(101.0,110.0,'关键结论可以追溯到证据、来源、时间和数据质量。'),
(110.0,117.5,'Critic 还会主动寻找：这个结论为什么可能不成立。'),
(117.5,124.0,'MountainGuardian 不让大模型直接预测灾害。'),
(124.0,128.0,'让 AI 知道答案从哪里来，也知道自己不能说什么。')]
def ts(x):
 h=int(x//3600); x-=h*3600; m=int(x//60); x-=m*60; s=int(x); ms=round((x-s)*1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'
o=[]
for i,(a,b,t) in enumerate(c,1): o += [str(i),f'{ts(a)} --> {ts(b)}',t,'']
Path(sys.argv[1]).write_text('\n'.join(o),encoding='utf-8')
PY

# Mix female narration at editorial offsets.
ffmpeg -y -loglevel error \
  -i "$TMP/visual.mp4" -i "$TMP/ambient.wav" \
  -i "$VO/vo1.mp3" -i "$VO/vo2.mp3" -i "$VO/vo3.mp3" -i "$VO/vo4.mp3" -i "$VO/vo5.mp3" -i "$VO/vo6.mp3" \
  -filter_complex "[1:a]volume=0.16[bed];[2:a]adelay=4600|4600[v2];[3:a]adelay=17200|17200[v3];[4:a]adelay=29500|29500[v4];[5:a]adelay=53000|53000[v5];[6:a]adelay=85500|85500[v6];[7:a]adelay=117500|117500[v7];[bed][v2][v3][v4][v5][v6][v7]amix=inputs=7:duration=longest:normalize=0,alimiter=limit=0.95[a]" \
  -map 0:v:0 -map "[a]" \
  -vf "subtitles=$OUT/subtitles.srt:fontsdir=/usr/share/fonts/opentype/noto:force_style='FontName=Noto Sans CJK SC,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=40,Alignment=2'" \
  -t "$TOTAL" -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT/MountainGuardian_Competition_Demo_v0.2.mp4"

python3 - "$OUT" <<'PY'
import json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1]); f=out/'MountainGuardian_Competition_Demo_v0.2.mp4'
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size,format_name','-show_entries','stream=codec_name,width,height,r_frame_rate','-of','json',str(f)],text=True))
d=float(p['format']['duration']); sz=int(p['format']['size'])
s=(out/'subtitles.srt').read_text(encoding='utf-8')
banned=['王馨逸','学校','指导教师','预测准确率','官方预警']
h=[x for x in banned if x in s]
ok=d<=150 and sz<=200*1024*1024 and not h
r=f'PASS={ok}\nDuration={d:.3f}s / 150s\nSize={sz/1048576:.2f} MB / 200MB\nFormat={p["format"].get("format_name")}\nStreams={p.get("streams")}\nAnonymity/science banned hits={h}\nOpening footage: public-domain Gyirong Port mudslide CCTV, 2026-08-26.\nNo persistent editorial overlay. Stable product shots: no zoompan.\nFemale Mandarin voice: zh-CN-XiaoxiaoNeural.\n91/100 is Baseline Susceptibility, not event probability.\n'
(out/'QA_REPORT.txt').write_text(r,encoding='utf-8'); print(r)
raise SystemExit(0 if ok else 2)
PY
