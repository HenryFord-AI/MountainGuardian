#!/usr/bin/env python3
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path(__file__).resolve().parent/'satellite'
OUT.mkdir(exist_ok=True)
FILES={
    '01_sentinel2_pre_20260824.jpg':'https://live.spacedaily.com.cn/gyirong/satellite/sentinel2-pre.jpg',
    '02_sentinel2_post_20260827.jpg':'https://live.spacedaily.com.cn/gyirong/satellite/sentinel2-post.jpg',
    '03_glacier_distribution_official.jpg':'https://www.igm.cgs.gov.cn/mobile/kjdt/202609/W020260903364698961335.jpg',
    '04_disaster_path_official.jpg':'https://www.igm.cgs.gov.cn/mobile/kjdt/202609/W020260903364698987537.jpg',
    '05_pre_post_ground_photo_official.jpg':'https://www.igm.cgs.gov.cn/mobile/kjdt/202609/W020260903364698946137.jpg',
}
for name,url in FILES.items():
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urlopen(req,timeout=30) as r:
            data=r.read()
        (OUT/name).write_bytes(data)
        print('OK',name,len(data))
    except Exception as e:
        print('FAIL',name,e)
