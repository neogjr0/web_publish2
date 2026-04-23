import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
from urllib.parse import unquote
import json
import random

# ==========================================
# [1] 설정 - 인증키는 현태님 키 그대로 유지
# ==========================================
API_KEY = '7b6efd99b84e03fca06677a5f9632db682bac3e47d90f5ec37f3b4947e84307e'

# 💡 [자동화] TARGET_MONTH 자동 계산 (지난달 기준)
# 매달 초(예: 1일)에 실행되므로, 지난달 데이터를 수집하는 것이 정석입니다.
yesterday = datetime.now() - timedelta(days=20) # 넉넉히 20일 전 날짜 계산
TARGET_MONTH = yesterday.strftime('%Y%m')

# 서울시 25개 자치구 전체 리스트 (로테이션용)
SEOUL_ALL_DISTRICTS = {
    "강남구": "11680", "강동구": "11740", "강북구": "11305", "강서구": "11500",
    "관악구": "11620", "광진구": "11215", "구로구": "11530", "금천구": "11545",
    "노원구": "11350", "도봉구": "11320", "동대문구": "11230", "동작구": "11590",
    "마포구": "11440", "서대문구": "11410", "서초구": "11650", "성동구": "11200",
    "성북구": "11290", "송파구": "11710", "양천구": "11470", "영등포구": "11560",
    "용산구": "11170", "은평구": "11380", "종로구": "11110", "중구": "11140", "중랑구": "11260"
}

# 💡 [랜덤] 3단계 핵심: 실행 시마다 25개 중 5개 구 랜덤 추출
# 국토부 API 서버 연결 거부(10061) 방지를 위해 수집 범위를 적절히 조절합니다.
selected_districts = random.sample(list(SEOUL_ALL_DISTRICTS.keys()), 5)
target_list = {k: SEOUL_ALL_DISTRICTS[k] for k in selected_districts}

def fetch_api_data(lawd_cd, deal_ymd):
    # 포트 8081 없이 더 안정적인 최신 API 엔드포인트 사용
    url = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    params = {'serviceKey': unquote(API_KEY), 'LAWD_CD': lawd_cd, 'DEAL_YMD': deal_ymd, 'numOfRows': '200'}
    try:
        # 연결 거부(10061) 방지를 위해 요청 전 아주 짧은 휴식
        time.sleep(0.6) 
        res = requests.get(url, params=params, timeout=20)
        root = ET.fromstring(res.text)
        items = []
        for item in root.findall('.//item'):
            d = {child.tag: child.text.strip() if child.text else "" for child in item}
            # 데이터 전처리 (Pure Python)
            d['price'] = int(d.get('dealAmount', '0').replace(',', ''))
            d['area'] = float(d.get('excluUseAr', '0'))
            d['py'] = int(round(d['area'] / 3.3058))
            items.append(d)
        return items
    except Exception as e:
        print(f"❌ {lawd_cd} 호출 에러: {e}")
        return []

# [2] 데이터 수집 및 실거주 맞춤 분석 (Pure Python)
all_data = []
print(f"🔄 자동 로테이션 수집 시작... ({datetime.now().strftime('%H:%M')})")
print(f"📅 수집 월: {TARGET_MONTH}")
print(f"👉 이번 실행 대상: {' | '.join(selected_districts)}")

for name, code in target_list.items():
    res = fetch_api_data(code, TARGET_MONTH)
    for r in res:
        r['gu'] = name
        all_data.append(r)
    print(f"✅ {name} 완료 ({len(res)}건)")

if not all_data:
    print("‼️ 데이터 수집 실패. API 키를 확인하세요.")
    exit()

# 실거주 필터링 및 인기 단지 상위 30개 추출 (V3 로직 유지)
# 실거주 필터링 (가장 선호되는 국평구간: 50㎡~90㎡)
real_living_data = [r for r in all_data if 50 <= r['area'] <= 90]

# 인기 단지 분석 (동일 아파트/면적 기준 거래 건수)
apt_counts = {}
for r in real_living_data:
    key = f"{r['gu']} {r['aptNm']}" # 구이름을 붙여서 고유 단지 식별
    if key not in apt_counts:
        apt_counts[key] = {'count': 0, 'total_price': 0, 'data': r}
    apt_counts[key]['count'] += 1
    apt_counts[key]['total_price'] += r['price']

# 거래량 많은 단지 상위 30개 추출 (실거주 선호도 기준)
popular_list = sorted(apt_counts.values(), key=lambda x: x['count'], reverse=True)[:30]

# [3] 이원화 파일 설정
now = datetime.now()
specific_filename = f"seoul_real_use_{now.strftime('%Y%m%d')}.html"

# 차트 데이터 생성
gu_trend = {}
for r in real_living_data:
    gu_trend[r['gu']] = gu_trend.get(r['gu'], 0) + 1

# 현태님 맞춤 가독성 개선 HTML 콘텐츠 (V3 유지)
html_content = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Seoul Real-Use Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        body {{ background: #f1f5f9; color: #0f172a; font-family: 'Pretendard', sans-serif; font-size: 16px; }}
        .glass {{ background: white; border: 1px solid #e2e8f0; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); }}
        .card-hover:hover {{ border-color: #2563eb; transform: translateY(-4px); transition: all 0.3s ease; }}
        /* 가독성 보완을 위한 추가 스타일 */
        .text-price {{ color: #1e3a8a; }} 
        .text-count {{ color: #1d4ed8; }}
    </style>
</head>
<body class="p-4 md:p-10">
    <div class="max-w-5xl mx-auto">
        <header class="mb-12 flex justify-between items-end border-b-2 border-slate-200 pb-6 animate__animated animate__fadeInDown">
            <div>
                <h1 class="text-4xl font-black text-slate-950 tracking-tight">서울 <span class="text-blue-700">실거주</span> 트렌드</h1>
                <p class="text-lg text-slate-600 font-semibold mt-2">국민평형(59~84㎡) 실거래 및 인기 단지 리포트</p>
            </div>
            <p class="text-sm font-mono text-slate-500 bg-slate-100 px-3 py-1 rounded-full italic">{' | '.join(selected_districts)} | Updated: {now.strftime('%H:%M:%S')}</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12 animate__animated animate__fadeIn">
            <div class="md:col-span-2 glass p-8 rounded-3xl">
                <h2 class="text-sm font-bold text-slate-500 mb-5 uppercase tracking-widest border-l-4 border-blue-600 pl-3">구별 실거주용 거래량 비중</h2>
                <canvas id="volChart" height="140"></canvas>
            </div>
            <div class="glass p-8 rounded-3xl flex flex-col justify-center text-center">
                <span class="text-sm font-bold text-slate-500 mb-2 uppercase tracking-widest">이달의 실거주 거래</span>
                <span class="text-6xl font-black text-blue-700">{len(real_living_data)}<span class="text-3xl font-bold text-slate-600">건</span></span>
                <p class="text-xs text-slate-500 mt-3">서울 전역 50~90㎡ 기준</p>
            </div>
        </div>

        <h2 class="text-xl font-bold text-slate-950 mb-6 ml-1 flex items-center gap-3 animate__animated animate__fadeInLeft">
            <span class="text-2xl">🔥</span> 현재 가장 많이 팔리는 단지 (TOP 30)
        </h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            {"".join([f'''
            <div class="glass p-6 rounded-2xl card-hover flex justify-between items-center cursor-pointer animate__animated animate__fadeInUp" 
                 style="animation-delay: {i*0.02}s"
                 onclick="window.open('https://m.land.naver.com/search/result/{r['data']["gu"]} {r['data'].get("umdNm","")} {r['data']["aptNm"].split("(")[0]}')">
                <div class="flex-1 min-w-0 pr-4">
                    <div class="flex items-center gap-3 mb-2">
                        <span class="bg-blue-100 text-count text-xs px-3 py-1 rounded-full font-bold whitespace-nowrap">{r['count']}건 거래</span>
                        <h3 class="font-extrabold text-slate-950 text-lg truncate">{r['data']["aptNm"]}</h3>
                    </div>
                    <p class="text-sm text-slate-600 font-medium">{r['data']["gu"]} {r['data'].get("umdNm","")} · <span class="font-semibold text-slate-800">{int(r['data']["area"])}㎡ ({r['data']["py"]}평)</span></p>
                </div>
                <div class="text-right flex-shrink-0">
                    <p class="text-2xl font-black text-price tracking-tight">{(r['total_price']//r['count'])//10000}억<span class="text-xl font-bold"> {(r['total_price']//r['count'])%10000 if (r['total_price']//r['count'])%10000 > 0 else ""}</span></p>
                    <p class="text-xs text-slate-500 font-bold uppercase mt-1">평균 거래가</p>
                </div>
            </div>
            ''' for i, r in enumerate(popular_list)])}
        </div>
    </div>

    <script>
        const guData = {json.dumps(gu_trend, ensure_ascii=False)};
        Chart.defaults.font.size = 12;
        new Chart(document.getElementById('volChart'), {{
            type: 'bar',
            data: {{
                labels: Object.keys(guData),
                datasets: [{{
                    label: '거래량',
                    data: Object.values(guData),
                    backgroundColor: '#1d4ed8',
                    borderRadius: 6
                }}]
            }},
            options: {{
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ 
                    x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11, weight: 'bold' }}, color: '#475569' }} }},
                    y: {{ grid: {{ color: '#e2e8f0' }}, ticks: {{ font: {{ size: 12 }} }}, color: '#64748b' }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""

# [4] 이원화 파일 저장 로직 복구 (V3 유지)
with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)
with open(specific_filename, "w", encoding="utf-8") as f: f.write(html_content)
print(f"✅ 자동 업데이트 완료!")