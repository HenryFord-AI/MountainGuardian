python3 - "$OUT/subtitles.srt" <<'PY'
import sys
from pathlib import Path
c=[
(0.8,6.5,'\u5728\u9ad8\u5c71\u5ce1\u8c37\u91cc\uff0c\u98ce\u9669\u4ece\u6765\u4e0d\u53ea\u662f\u4e00\u4e2a\u6570\u5b57\u3002'),
(6.5,13.2,'\u5730\u5f62\u3001\u51b0\u5ddd\u3001\u964d\u6c34\u3001\u9065\u611f\u548c\u5386\u53f2\u707e\u5bb3\u5171\u540c\u4f5c\u7528\u3002'),
(14.6,20.6,'\u8fd9\u5c31\u662f MountainGuardian\uff0c\u5c71\u6cb3\u5b88\u671b\u8005\u3002'),
(20.6,27.3,'\u4e0d\u540c\u4e13\u4e1a\u7684 AI\uff0c\u50cf\u4e00\u4e2a\u53d7\u7ea6\u675f\u7684\u7814\u7a76\u56e2\u961f\u4e00\u6837\u534f\u540c\u5de5\u4f5c\u3002'),
(29.0,36.0,'\u5148\u770b\u4e00\u6b21\u771f\u5b9e\u707e\u5bb3\uff1a\u7cfb\u7edf\u53ea\u8bfb\u53d6\u707e\u524d\u53ef\u83b7\u5f97\u7684\u8bc1\u636e\u3002'),
(36.0,44.0,'91 / 100 \u662f\u57fa\u7ebf\u6613\u611f\u6027\u6307\u6570\uff0c\u4e0d\u662f 91% \u7684\u53d1\u751f\u6982\u7387\u3002'),
(44.0,51.2,'\u7ed3\u679c\u5148\u51bb\u7ed3\uff0c\u4e4b\u540e\u624d\u6253\u5f00\u707e\u540e\u8bc1\u636e\u8fdb\u884c\u9a8c\u8bc1\u3002'),
(53.0,61.0,'Risk Watch \u83b7\u53d6\u5f53\u524d\u73af\u5883\u6570\u636e\uff0c\u5e76\u5b8c\u6210\u6807\u51c6\u5316\u4e0e\u8d28\u91cf\u68c0\u67e5\u3002'),
(61.0,70.0,'\u6570\u636e\u7f3a\u5931\u6216\u6a21\u578b\u4e0d\u53ef\u7528\u65f6\uff0c\u7cfb\u7edf\u4f1a\u660e\u786e\u6807\u8bb0\u8df3\u8fc7\u6216\u56de\u9000\u3002'),
(70.0,78.0,'\u98ce\u9669\u6307\u6570\u7531\u786e\u5b9a\u6027\u6a21\u578b\u8ba1\u7b97\uff0c\u4e0d\u7531\u5927\u6a21\u578b\u81ea\u7531\u751f\u6210\u3002'),
(78.0,88.2,'Synthesizer \u8d1f\u8d23\u7efc\u5408\uff0cCritic \u8d1f\u8d23\u68c0\u67e5\u8bc1\u636e\u3001\u8fc7\u5ea6\u63a8\u65ad\u548c\u79d1\u5b66\u8fb9\u754c\u3002'),
(89.8,98.0,'AI \u7ed9\u51fa\u7ed3\u679c\uff0c\u4e0d\u7b49\u4e8e\u6211\u4eec\u5c31\u5e94\u8be5\u76f4\u63a5\u76f8\u4fe1\u5b83\u3002'),
(98.0,106.0,'\u5173\u952e\u7ed3\u8bba\u53ef\u4ee5\u8ffd\u6eaf\u5230\u8bc1\u636e\u3001\u6765\u6e90\u3001\u65f6\u95f4\u548c\u6570\u636e\u8d28\u91cf\u3002'),
(106.0,114.2,'Critic \u8fd8\u4f1a\u4e3b\u52a8\u5bfb\u627e\uff1a\u8fd9\u4e2a\u7ed3\u8bba\uff0c\u4e3a\u4ec0\u4e48\u53ef\u80fd\u4e0d\u6210\u7acb\u3002'),
(115.0,122.5,'MountainGuardian \u4e0d\u8ba9\u5927\u6a21\u578b\u76f4\u63a5\u9884\u6d4b\u707e\u5bb3\u3002'),
(122.5,130.2,'\u8ba9 AI \u4e0d\u53ea\u7ed9\u51fa\u7b54\u6848\uff0c\u4e5f\u77e5\u9053\u7b54\u6848\u4ece\u54ea\u91cc\u6765\uff0c\u66f4\u77e5\u9053\u81ea\u5df1\u4e0d\u80fd\u8bf4\u4ec0\u4e48\u3002')]
def ts(x):
 h=int(x//3600); x-=h*3600; m=int(x//60); x-=m*60; s=int(x); ms=round((x-s)*1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'
o=[]
for i,(a,b,t) in enumerate(c,1): o += [str(i),f'{ts(a)} --> {ts(b)}',t,'']
Path(sys.argv[1]).write_text('\n'.join(o),encoding='utf-8')
PY

# Mix narration chapters at their exact editorial offsets and burn subtitles.
ffmpeg -y -loglevel error \
  -i "$TMP/visual.mp4" -i "$TMP/ambient.wav" \
  -i "$VO/vo1.mp3" -i "$VO/vo2.mp3" -i "$VO/vo3.mp3" -i "$VO/vo4.mp3" -i "$VO/vo5.mp3" -i "$VO/vo6.mp3" \
  -filter_complex "[1:a]volume=0.14[bed];[2:a]adelay=800|800[v2];[3:a]adelay=14600|14600[v3];[4:a]adelay=29000|29000[v4];[5:a]adelay=53000|53000[v5];[6:a]adelay=89800|89800[v6];[7:a]adelay=115000|115000[v7];[bed][v2][v3][v4][v5][v6][v7]amix=inputs=7:duration=longest:normalize=0,alimiter=limit=0.95[a]" \
  -map 0:v:0 -map "[a]" \
  -vf "subtitles=$OUT/subtitles.srt:fontsdir=/usr/share/fonts/opentype/noto:force_style='FontName=Noto Sans CJK SC,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=42,Alignment=2'" \
  -t "$TOTAL" -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT/MountainGuardian_Competition_Demo_v0.1.mp4"

python3 - "$OUT" <<'PY'
import json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1]); f=out/'MountainGuardian_Competition_Demo_v0.1.mp4'
p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size,format_name','-show_entries','stream=codec_name,width,height,r_frame_rate','-of','json',str(f)],text=True))
d=float(p['format']['duration']); sz=int(p['format']['size'])
s=(out/'subtitles.srt').read_text(encoding='utf-8')
banned=['\u738b\u99a8\u9038','\u5b66\u6821','\u6307\u5bfc\u6559\u5e08','\u9884\u6d4b\u51c6\u786e\u7387','\u5b98\u65b9\u9884\u8b66']
h=[x for x in banned if x in s]
ok=d<=150 and sz<=200*1024*1024 and not h
r=f'PASS={ok}\nDuration={d:.3f}s / 150s\nSize={sz/1048576:.2f} MB / 200MB\nFormat={p["format"].get("format_name")}\nStreams={p.get("streams")}\nAnonymity/science banned hits={h}\nProduction state shown truthfully, including skip/fallback states.\n91/100 is Baseline Susceptibility, not event probability.\n'
(out/'QA_REPORT.txt').write_text(r,encoding='utf-8'); print(r)
raise SystemExit(0 if ok else 2)
PY
