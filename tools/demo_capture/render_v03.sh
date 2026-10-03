#!/usr/bin/env bash
set -euo pipefail

CAP=artifacts/demo_capture
OUT=artifacts/final_demo_v03
VO="$OUT/voice"
TMP="$OUT/tmp"
mkdir -p "$VO" "$TMP"
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
BOLD=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
TOTAL=140

# Opening visuals: NASA/NPS public science and hazard media.
GLACIER_URL='https://svs.gsfc.nasa.gov/vis/a010000/a011000/a011030/11030_columbia_1986-2011_timelapse_appletv.webmhd.webm'
RAIN_URL='https://svs.gsfc.nasa.gov/vis/a000000/a004300/a004369/GPM_Fleet_IMERG_new_1080p_30.webm'
LANDSLIDE_URL='https://svs.gsfc.nasa.gov/vis/a020000/a020200/a020226/Landslide_final_59fps_prores.webm'
DEBRIS_URL='https://commons.wikimedia.org/wiki/Special:Redirect/file/Debris_Flows_Through_Bright_Angel_Creek_(55504603393).webm'

curl -L --fail --retry 3 "$GLACIER_URL" -o "$TMP/glacier.webm"
curl -L --fail --retry 3 "$RAIN_URL" -o "$TMP/rain.webm"
curl -L --fail --retry 3 "$LANDSLIDE_URL" -o "$TMP/landslide.webm"
curl -L --fail --retry 3 "$DEBRIS_URL" -o "$TMP/debris.webm"

# Film title, four-shot meaning montage, then product.
ffmpeg -y -loglevel error -f lavfi -i color=c=0x02070d:s=1920x1080:r=30:d=4 \
  -vf "drawtext=fontfile=${BOLD}:text='山河守望者':x=(w-text_w)/2:y=430:fontsize=86:fontcolor=white:alpha='if(lt(t,1.2),t/1.2,if(lt(t,3.2),1,(4-t)/0.8))',drawtext=fontfile=${FONT}:text='MOUNTAINGUARDIAN':x=(w-text_w)/2:y=550:fontsize=28:fontcolor=0x8fcde8:alpha='if(lt(t,1.5),t/1.5,if(lt(t,3.2),1,(4-t)/0.8))',format=yuv420p" \
  -an -c:v libx264 -r 30 -preset veryfast -crf 19 -pix_fmt yuv420p "$TMP/s0.mp4"

clip() {
  local src="$1" out="$2" ss="$3" dur="$4"
  ffmpeg -y -loglevel error -ss "$ss" -t "$dur" -i "$src" \
    -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,eq=contrast=1.05:saturation=0.88,fade=t=in:st=0:d=0.25,fade=t=out:st=$(python3 - <<PY
print(max(0,float('$dur')-0.30))
PY
):d=0.30,format=yuv420p" -an -c:v libx264 -r 30 -preset veryfast -crf 20 -pix_fmt yuv420p "$out"
}
clip "$TMP/glacier.webm" "$TMP/s1.mp4" 1.0 3.5
clip "$TMP/rain.webm" "$TMP/s2.mp4" 7.0 3.5
clip "$TMP/landslide.webm" "$TMP/s3.mp4" 0.4 3.5
clip "$TMP/debris.webm" "$TMP/s4.mp4" 2.0 3.5

stable_still() {
  local img="$1" out="$2" dur="$3"
  ffmpeg -y -loglevel error -loop 1 -i "$img" -t "$dur" \
    -vf "scale=1920:1080,fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st=$(python3 - <<PY
print(max(0,float('$dur')-0.30))
PY
):d=0.30,format=yuv420p" -an -c:v libx264 -r 30 -preset veryfast -crf 19 -pix_fmt yuv420p "$out"
}

# 18-36 overview: product meaning. 36-60 historical. 60-93 live risk scan.
stable_still "$CAP/01_overview.png" "$TMP/s5.mp4" 18
stable_still "$CAP/02_historical_replay.png" "$TMP/s6.mp4" 24
ffmpeg -y -loglevel error -ss 28.5 -t 33 -i "$CAP/poc_full_session.webm" \
  -vf "scale=1920:1080,fps=30,fade=t=in:st=0:d=0.25,fade=t=out:st=32.5:d=0.5,format=yuv420p" \
  -an -c:v libx264 -r 30 -preset veryfast -crf 20 -pix_fmt yuv420p "$TMP/s7.mp4"
stable_still "$CAP/07_intelligence_center.png" "$TMP/s8.mp4" 8
stable_still "$CAP/08_evidence_center.png" "$TMP/s9.mp4" 8
stable_still "$CAP/09_audit_safety.png" "$TMP/s10.mp4" 8
stable_still "$CAP/10_overview_end.png" "$TMP/s11.mp4" 15

# Closing title mirrors opening.
ffmpeg -y -loglevel error -f lavfi -i color=c=0x02070d:s=1920x1080:r=30:d=8 \
  -vf "drawtext=fontfile=${BOLD}:text='山河守望者':x=(w-text_w)/2:y=390:fontsize=82:fontcolor=white:alpha='if(lt(t,1.4),t/1.4,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='MOUNTAINGUARDIAN':x=(w-text_w)/2:y=500:fontsize=27:fontcolor=0x8fcde8:alpha='if(lt(t,1.7),t/1.7,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='mountainguardian.cn':x=(w-text_w)/2:y=595:fontsize=25:fontcolor=0x9cafc1:alpha='if(lt(t,2.0),t/2.0,if(lt(t,6.8),1,(8-t)/1.2))',drawtext=fontfile=${FONT}:text='Opening visuals: NASA SVS / U.S. National Park Service':x=(w-text_w)/2:y=675:fontsize=16:fontcolor=0x617386:alpha='if(lt(t,2.3),t/2.3,if(lt(t,6.8),1,(8-t)/1.2))',format=yuv420p" \
  -an -c:v libx264 -r 30 -preset veryfast -crf 19 -pix_fmt yuv420p "$TMP/s12.mp4"

# Re-encode concat to constant 30fps: avoids any timing drift.
: > "$TMP/concat.txt"
for i in {0..12}; do printf "file '%s'\n" "$(realpath "$TMP/s${i}.mp4")" >> "$TMP/concat.txt"; done
ffmpeg -y -loglevel error -f concat -safe 0 -i "$TMP/concat.txt" \
  -vf "fps=30,format=yuv420p" -an -c:v libx264 -r 30 -preset veryfast -crf 20 "$TMP/visual.mp4"

# Natural Mandarin narration: sentence-level synthesis. Subtitle times come from actual audio durations,
# not guessed timecodes, so text and voice remain locked together.
cat > "$TMP/build_voice.py" <<'PY'
import json, subprocess, sys
from pathlib import Path
out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=True)
sections=[
(4.35,[
'在高山峡谷里，灾害很少是突然出现的。',
'冰川变化、山体松动、持续降雨，往往在不同时间里慢慢叠加。',
'真正困难的，是把这些分散的信号拼成一幅能看懂的风险图景。']),
(19.2,[
'山河守望者想做的，就是让人工智能像一支小型研究团队。',
'有人看冰川和地质，有人看天气和水文，有人看遥感；最后，还要有人专门挑错。',
'不是一个模型拍脑袋，而是让证据彼此印证。']),
(36.4,[
'我们先把系统放回吉隆八二六灾害发生之前。',
'它只能看到当时能获得的数据，不能偷看灾后的答案。',
'系统得到九十一分的基线易感性指数。',
'这个九十一分不是发生概率，而是说明这里原本就有较高的基础易灾条件。',
'结果先锁定，之后才打开灾后资料进行验证。']),
(60.5,[
'历史案例看方法是否站得住；风险监测，则看它今天能不能工作。',
'点击扫描，系统重新收集当前数据、检查质量，再让不同专业智能体分别分析。',
'风险分数由固定模型计算，不让大模型凭感觉生成。',
'人工智能负责读证据、找联系、解释原因。',
'数据缺失时，系统会直接说出来，而不是假装完整。']),
(93.2,[
'最后，风险综合智能体把不同分析放在一起，评审智能体再反过来挑毛病。',
'证据够不够？有没有说过头？',
'点开证据中心，每个关键判断都能找到来源、时间和质量记录。']),
(116.5,[
'山河守望者不是替人宣布灾害会不会发生，而是帮助人更清楚地看见风险条件怎样变化。',
'让人工智能会分析，也会复核；会给答案，也知道什么时候应该说：我还不能确定。'])]

def dur(p):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True).strip())

def ts(x):
    h=int(x//3600); x-=h*3600; m=int(x//60); x-=m*60; s=int(x); ms=round((x-s)*1000)
    if ms==1000: s+=1; ms=0
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

items=[]; idx=0
for section_start,sents in sections:
    cursor=section_start
    for sent in sents:
        idx+=1; p=out/f'v{idx:02d}.mp3'
        subprocess.run(['edge-tts','--voice','zh-CN-XiaoxiaoNeural','--rate=+2%','--text',sent,'--write-media',str(p)],check=True)
        d=dur(p)
        items.append((p,cursor,d,sent))
        cursor += d+0.16

# Build an exact narration timeline.
cmd=['ffmpeg','-y','-loglevel','error']
for p,_,_,_ in items: cmd += ['-i',str(p)]
filters=[]; labels=[]
for i,(_,start,_,_) in enumerate(items):
    ms=round(start*1000); filters.append(f'[{i}:a]adelay={ms}|{ms}[a{i}]'); labels.append(f'[a{i}]')
filters.append(''.join(labels)+f'amix=inputs={len(items)}:duration=longest:normalize=0,alimiter=limit=0.95[narr]')
cmd += ['-filter_complex',';'.join(filters),'-map','[narr]','-c:a','pcm_s16le',str(out/'narration.wav')]
subprocess.run(cmd,check=True)

srt=[]
for n,(_,start,d,sent) in enumerate(items,1):
    srt += [str(n),f'{ts(start)} --> {ts(start+d)}',sent,'']
(out/'subtitles.srt').write_text('\n'.join(srt),encoding='utf-8')
meta={'items':[{'start':s,'duration':d,'text':t} for _,s,d,t in items], 'last_end':max(s+d for _,s,d,_ in items)}
(out/'voice_timing.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
PY
python3 "$TMP/build_voice.py" "$VO"
cp "$VO/subtitles.srt" "$OUT/subtitles.srt"
cp "$VO/voice_timing.json" "$OUT/voice_timing.json"

# Subtle ambient bed: no purchased music.
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=48:duration=${TOTAL}:sample_rate=48000" \
  -f lavfi -i "sine=frequency=72:duration=${TOTAL}:sample_rate=48000" \
  -f lavfi -i "anoisesrc=color=pink:duration=${TOTAL}:sample_rate=48000" \
  -filter_complex "[0:a]volume=0.010[a0];[1:a]volume=0.004[a1];[2:a]lowpass=f=900,highpass=f=70,volume=0.009[a2];[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0,afade=t=in:st=0:d=2,afade=t=out:st=137:d=3[bed]" \
  -map "[bed]" -c:a pcm_s16le "$TMP/ambient.wav"

# Mix narration and bed; burn subtitles generated from real TTS durations.
ffmpeg -y -loglevel error -i "$TMP/visual.mp4" -i "$TMP/ambient.wav" -i "$VO/narration.wav" \
  -filter_complex "[1:a]volume=0.15[bed];[2:a]volume=1.0[narr];[bed][narr]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]" \
  -map 0:v:0 -map '[a]' \
  -vf "subtitles=$OUT/subtitles.srt:fontsdir=/usr/share/fonts/opentype/noto:force_style='FontName=Noto Sans CJK SC,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=40,Alignment=2'" \
  -t "$TOTAL" -c:v libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT/MountainGuardian_Competition_Demo_v0.3.mp4"

python3 - "$OUT" <<'PY'
import json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1]); f=out/'MountainGuardian_Competition_Demo_v0.3.mp4'
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size,format_name','-show_entries','stream=codec_name,width,height,r_frame_rate','-of','json',str(f)],text=True))
d=float(p['format']['duration']); sz=int(p['format']['size'])
s=(out/'subtitles.srt').read_text(encoding='utf-8')
banned=['王馨逸','学校','指导教师','预测准确率','官方预警','91%']
h=[x for x in banned if x in s]
t=json.loads((out/'voice_timing.json').read_text(encoding='utf-8'))
ok=d<=150 and sz<=200*1024*1024 and not h and t['last_end']<=134
r=(f'PASS={ok}\nDuration={d:.3f}s / 150s\nSize={sz/1048576:.2f} MB / 200MB\n'
   f'Voice last end={t["last_end"]:.2f}s\nSubtitle timing=derived from actual TTS durations\n'
   f'Format={p["format"].get("format_name")}\nStreams={p.get("streams")}\n'
   f'Anonymity/science banned hits={h}\nNarration contains no English product jargon.\n')
(out/'QA_REPORT.txt').write_text(r,encoding='utf-8'); print(r)
raise SystemExit(0 if ok else 2)
PY
