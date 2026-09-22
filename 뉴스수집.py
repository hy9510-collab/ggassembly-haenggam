# -*- coding: utf-8 -*-
"""
행정사무감사 — 기관·부서별 언론보도 자동 수집
 - 구글 뉴스 검색(RSS, 인증키 불필요)으로 최근 7일 기사를 기관·부서 키워드별로 검색
 - 결과를 data/news.json 에 누적하고, 페이지용 data/news_data.js 를 다시 만든다
 - 실행: 뉴스수집.bat 더블클릭 (또는 Claude 예약작업이 매일 자동 실행)
"""
import json, os, re, sys, time, html
import urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
KST = timezone(timedelta(hours=9))
KEEP_DAYS = 400          # 이보다 오래된 기사는 정리

# ── 기관·부서별 검색어 ──
#  q   : 구글 뉴스 검색어 (따옴표 = 정확히 일치)
#  must: 제목·요약에 이 중 하나가 들어 있어야 채택 (엉뚱한 기사 거르기용, 없으면 무조건 채택)
QUERIES = {
 'guk': [dict(q='"경기도의회" "문화체육관광위원회"', must=['문화체육관광위원회', '문체위']), dict(q='경기도 "문화체육관광국"'),
         dict(q='경기도의회 문체위', must=['문화체육관광', '문체위']),
         dict(q='"문화체육관광" 경기도의원', must=['경기도의원', '경기도의회', '도의원']),
         dict(q='"문화체육관광" 경기도 예산', must=['경기도'])],
 'd-munhwa': [dict(q='"컬처패스"', must=['경기']), dict(q='"청년문화예술패스" 경기', must=['경기']),
              dict(q='"문화누리카드" OR "통합문화이용권"', must=['경기']), dict(q='"평택박물관"'), dict(q='"공립박물관" OR "문예회관" OR "문화의 날" OR "경기사진센터"', must=['경기']),
              dict(q='경기도 "문화정책과"', must=['경기'])],
 'd-religion': [dict(q='"전통사찰"', must=['경기']), dict(q='경기도 "종교협력과"'),
                dict(q='경기도 "종교문화시설"', must=['경기'])],
 'd-contents': [dict(q='경기도 "콘텐츠산업과"'), dict(q='경기도 "게임산업"', must=['경기도']),
                dict(q='"경기국제웹툰페어" OR "경기인디뮤직페스티벌" OR "AI 콘텐츠 어워즈"'),
                dict(q='"IP 융복합 콘텐츠 클러스터" 고양')],
 'd-arts': [dict(q='"예술인 기회소득" OR "예술인기회소득"'), dict(q='경기도 "예술정책과"'),
            dict(q='"상주단체"', must=['경기']), dict(q='"경기민예총"', must=['기회소득', '예술인', '도의회'])],
 'd-sports': [dict(q='"체육인 기회소득" OR "체육인기회소득"'), dict(q='"직장운동경기부"', must=['경기도']),
              dict(q='"경기도 선수촌"'), dict(q='경기도 "체육진흥과"'), dict(q='"팀업캠퍼스"'), dict(q='"국민체육센터" OR "공공체육시설" OR "체육시설"', must=['경기도'])],
 'd-heritage': [dict(q='"국가유산" OR "문화유산"', must=['경기도']),
                dict(q='"한양의 수도성곽" OR "북한산성"', must=['세계유산']), dict(q='"무형유산"', must=['경기']),
                dict(q='"문화유산돌봄" 경기', must=['경기'])],
 'd-tour': [dict(q='경기도 "관광산업과"'), dict(q='"경기대표관광축제" OR "경기도 대표축제"'),
            dict(q='"마이스" OR "웰니스 관광" OR "웰니스관광"', must=['경기']), dict(q='"영화동 문화관광지구" OR "영화동 관광지구" OR "영화지구"'),
            dict(q='"외래관광객" OR "외국인 관광객"', must=['경기도']),
            dict(q='"경기관광" OR "경기도 관광"'), dict(q='"경기도" 관광', must=['경기도, ', '경기도가', '경기도는', '경기도 관광'])],
 'd-games': [dict(q='"2027 전국체전" OR "2027년 전국체전" OR "2027 전국체육대회"'), dict(q='"제108회 전국체육대회"'),
             dict(q='경기도 "전국체전추진단"')],
 'a-gto': [dict(q='"경기관광공사"')],
 'a-ggcf': [dict(q='"경기문화재단"'),
            dict(q='"경기도박물관" OR "경기도미술관" OR "백남준아트센터" OR "실학박물관" OR "전곡선사박물관"'),
            dict(q='"경기도어린이박물관" OR "경기북부어린이박물관" OR "경기역사문화유산원" OR "경기상상캠퍼스"')],
 'a-ggac': [dict(q='"경기아트센터"'), dict(q='"경기필하모닉" OR "경기도극단" OR "경기도무용단" OR "경기시나위"')],
 'a-gcon': [dict(q='"경기콘텐츠진흥원" OR "경콘진"'), dict(q='"플레이엑스포" 경기', must=['경기'])],
 'a-kocef': [dict(q='"한국도자재단"'), dict(q='"경기도자비엔날레"')],
 'a-swc': [dict(q='"수원월드컵경기장관리재단" OR "월드컵재단" OR "수원월드컵경기장"'), dict(q='"우만테크노밸리"')],
 'a-ggsports': [dict(q='"경기도체육회"')],
 'a-psg': [dict(q='"경기도장애인체육회"')],
 'a-dmz': [dict(q='"DMZ국제다큐" OR "DMZ Docs" OR "DMZ다큐"')],
 'a-namhan': [dict(q='"남한산성세계유산센터"'), dict(q='"남한산성"', must=['행궁', '세계유산', '경기도', '문화제', '성곽'])],
}

# 의원 질의·지적 기사: 제목에 기관명이 없는 경우가 많아 '의회어 + 분야어'가 함께 있으면 채택
COUNCIL = ['경기도의원', '경기도의회', '도의원', '문체위', '문화체육관광위']
NOT_GG = ['시의회', '군의회', '구의회', '시의원', '인천', '부산', '서울시', '대구', '광주광역', '대전', '울산', '세종',
          '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '국회의원', '사회적경제', '신용보증', '기후행동',
          '공무원 체육', '교육청', '교육감']
TOPIC = ['문화', '체육', '관광', '예술', '콘텐츠', '유산', '박물관', '미술관', '축제', '기회소득', '예술인', '체육인', '전국체전', '문화재단',
         '아트센터', '관광공사', '체육회', '콘텐츠진흥원', '도자', '영화제', '컬처패스', '남한산성', '웹툰', '게임', '공연']
for _qd in QUERIES['guk']:
    _qd['exclude'] = NOT_GG
QUERIES['guk'] += [dict(q=q, noquote=True, all=[COUNCIL, TOPIC], exclude=NOT_GG) for q in [
    '경기도의회 문화체육관광위원회', '경기도의원 문화 지적', '경기도의원 체육 지적', '경기도의원 관광 지적',
    '경기도의원 예술 촉구', '경기도의원 문화예술 예산', '경기도의원 체육 예산', '"황대호" 위원장', '"채신덕" 위원장',
    '경기도의회 문체위 질타', '경기도의원 재단 지적', '경기도의원 기회소득']]
# 도 문화·체육·관광 예산·정책 전반 기사(기관명·의원명 없이 나오는 경우)
QUERIES['guk'] += [dict(q=q, noquote=True, all=[['경기도', '경기 '], ['문화', '체육', '관광', '예술'], ['예산', '삭감', '감액', '추경', '재정']],
                        exclude=NOT_GG) for q in [
    '경기도 문화예술 예산 삭감', '경기도 문화 예산 감액', '경기도 체육 예산 삭감', '경기도 관광 예산 삭감',
    '경기도 문화체육관광 예산', '경기도 예술계 반발 예산']]


# ── 분야 정책·쟁점(기관과 무관한 문화·체육·관광 분야 전반) ──
#   f-policy : 정부 문화체육관광 정책·예산   f-local : 지자체 문화재정·문화기관 전반
FIELD_Q = {
 'f-policy': [('"문화체육관광부" 정책', ['문화체육관광부', '문체부']), ('"문체부" 예산', ['문체부', '문화체육관광부']),
              ('"문화체육관광부" 보도자료 OR 발표', ['문화체육관광부', '문체부']),
              ('"지역문화진흥" OR "문화도시"', ['지역문화', '문화도시']),
              ('"문화누리카드" OR "청년문화예술패스" OR "청년문화패스"', ['문화누리', '청년문화']),
              ('국정과제 문화 OR 체육 OR 관광', ['국정과제'])],
 'f-arts': [('"예술인 복지" OR "예술인복지법"', ['예술인']), ('"예술활동증명" OR "창작준비금" OR "예술활동준비금"', ['예술']),
            ('예술 "표준계약서"', ['표준계약서']), ('"건축물 미술작품" OR "공공미술" 제도', ['미술작품', '공공미술']),
            ('"예술인 고용보험" OR "예술인 기본소득"', ['예술인'])],
 'f-sports': [('"스포츠윤리센터"', ['스포츠윤리센터']), ('"체육회" 비위 OR 징계 OR 감사', ['체육회']),
              ('"학교운동부" OR "학교체육" 정책', ['학교운동부', '학교체육']),
              ('"생활체육" 정책 OR 예산', ['생활체육']), ('"공공체육시설" 안전 OR 개보수', ['체육시설']),
              ('"체육인 복지" OR "은퇴 선수" 지원', ['체육인', '은퇴'])],
 'f-tour': [('"관광진흥법" OR "관광진흥기금"', ['관광진흥']), ('"외래관광객" OR "방한 관광객" 정책', ['관광객']),
            ('"지역관광" OR "관광거점도시" 정책', ['지역관광', '관광거점']), ('"마이스" 산업 육성', ['마이스', 'MICE']),
            ('"야영장" OR "관광숙박" 안전점검', ['야영장', '관광숙박'])],
 'f-contents': [('"K-콘텐츠" 정책 OR 예산', ['콘텐츠']), ('"게임산업진흥" OR "게임산업법"', ['게임산업']),
                ('"영화진흥위원회" OR "국제영화제" 지원 OR 예산', ['영화']), ('"웹툰" 산업 정책 OR 지원', ['웹툰']),
                ('콘텐츠 "저작권" 정책 OR AI', ['저작권'])],
 'f-heritage': [('"국가유산청" 정책 OR 예산', ['국가유산']), ('"세계유산" 등재 OR 보존 관리', ['세계유산']),
                ('"무형유산" 전승 OR 지원', ['무형유산']), ('"국가유산" 안전 OR "문화유산돌봄"', ['국가유산', '문화유산'])],
 'f-local': [('지자체 "문화예산" 삭감 OR 축소', ['문화예산']), ('"문화재단" 출연금 OR 구조조정', ['문화재단']),
             ('"지역축제" 예산 OR 안전 OR 논란', ['지역축제', '축제']), ('공공기관 인건비 "체불" OR 미편성', ['인건비', '체불']),
             ('시도의회 "문화체육관광위원회"', ['문화체육관광위원회'])],
}
# 광고·도박·스포츠중계 등 스팸 제목/매체 차단
SPAM = ['토토', '카지노', '배팅', '베팅', '먹튀', '슬롯', '바카라', '무료시청', '다시보기', '중계', '픽스터', '꽁머니',
        '성인', '출장', '대출', '코인 리딩', '릴게임']
for _uid, _qs in FIELD_Q.items():
    QUERIES[_uid] = [dict(q=_q, must=_must, exclude=SPAM) for _q, _must in _qs]

# 문화체육관광부 보도자료(누리집 직접 수집)
MCST_LIST = 'https://www.mcst.go.kr/kor/s_notice/press/pressList.jsp'
MCST_VIEW = 'https://www.mcst.go.kr/kor/s_notice/press/pressView.jsp?pSeq='


def fetch_mcst(pages=2):
    """문체부 보도자료 목록에서 제목·링크·날짜 수집 → [(title, url, date)]"""
    out = []
    for pg in range(1, pages + 1):
        url = MCST_LIST + ('?pCurrentPage=%d' % pg if pg > 1 else '')
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode('utf-8', 'ignore')
        except Exception as e:
            print('  ! 문체부 보도자료 수집 실패:', e)
            break
        for m in re.finditer(r'href="[^"]*pressView\.jsp\?pSeq=(\d+)"[^>]*>(.*?)</a>', raw, re.S):
            seq, t = m.group(1), m.group(2)
            title = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html.unescape(t))).replace('새글', '').strip()
            # 날짜는 제목 링크 뒤쪽(같은 행)에서 가장 먼저 나오는 날짜를 사용
            dm = re.search(r'(20\d\d)[.\-](\d\d)[.\-](\d\d)', raw[m.end(): m.end() + 600])
            date = '-'.join(dm.groups()) if dm else None
            if title and len(title) > 6:
                out.append((title, MCST_VIEW + seq, date))
        time.sleep(0.6)
    return out

# 제목에 이 단어가 있으면 해당 기관·부서 기사로도 분류
TITLE_MAP = {
 'a-gto': ['경기관광공사', '관광공사'], 'a-ggcf': ['경기문화재단', '문화재단'], 'a-ggac': ['경기아트센터', '아트센터'],
 'a-gcon': ['경기콘텐츠진흥원', '콘텐츠진흥원', '경콘진'], 'a-kocef': ['한국도자재단', '도자재단', '도자비엔날레'],
 'a-swc': ['월드컵재단', '월드컵경기장관리재단'], 'a-ggsports': ['경기도체육회'], 'a-psg': ['장애인체육회'],
 'a-dmz': ['DMZ국제다큐', 'DMZ다큐', 'DMZ영화제', 'DMZ Docs'], 'a-namhan': ['남한산성'],
 'd-arts': ['예술인 기회소득', '예술인기회소득'], 'd-sports': ['체육인 기회소득', '체육인기회소득', '직장운동경기부'],
 'd-munhwa': ['컬처패스', '평택박물관'], 'd-games': ['2027 전국체전', '2027년 전국체전', '제108회 전국체육대회'],
}

# 기사 성격 태그
TAGS = [
 ('보도자료', r'^$'),   # 보도자료는 수집 단계에서 직접 표시(제목 판별 아님)
 ('의회', r'도의회|도의원|의원[,은이 ]|행정사무감사|행감|상임위|문체위|예결위|추경|임시회|정례회'),
 ('쟁점', r'삭감|감액|논란|의혹|비위|갑질|감사원|징계|체불|농성|규탄|반발|파행|공석|부실|특혜|위반|고발|수사|송치|사퇴|폐지|중단|혈세|적자|'
          r'지적|질타|촉구|비판|문제\s?제기|질의|미흡|낭비|방만|파업|노조|해임|고소|횡령|폭행|폭력|성희롱|성추행|채용비리|부당|직권남용|'
          r'솜방망이|허술|혼선|차질|지연|표류|제자리|반토막|철회|항의|불공정|편법|쪼개기|유착|배임|감사\s?결과|시정\s?(요구|조치|명령)|경고\s?처분|주의\s?처분|기관\s?경고'),
 ('예산', r'예산|추경|출연금|보조금|억\s?원'),
]

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


DAYS = 7
ONLY, ONLY_NEW = [], False  # 특정 기관만 다시 수집할 때
WINDOW = None            # (시작일, 종료일) — 연도 소급 수집 때 월 단위로 지정

# 쟁점 기사 집중 검색어(기관명 검색에 덧붙임)
ISSUE_OR = '(논란 OR 삭감 OR 감액 OR 의혹 OR 비위 OR 갑질 OR 징계 OR 감사 OR 지적 OR 질타 OR 농성 OR 노조 OR 수사 OR 부실 OR 특혜 OR 공석)'


def fetch(q):
    span = f' after:{WINDOW[0]} before:{WINDOW[1]}' if WINDOW else f' when:{DAYS}d'
    url = ('https://news.google.com/rss/search?q=' + urllib.parse.quote(q + span) +
           '&hl=ko&gl=KR&ceid=KR:ko')
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
            return ET.fromstring(raw).findall('.//item')
        except Exception as e:
            err = e
            time.sleep(2 + attempt * 3)
    print('  ! 검색 실패:', q, err)
    return []


def clean_title(t, src):
    t = html.unescape(t or '').strip()
    if src and t.endswith(' - ' + src):
        t = t[: -len(src) - 3]
    return t.strip()


def _ns(t):
    return re.sub(r'\s+', '', t)


def relevant(qd, text):
    """구글이 따옴표를 무시하고 넓게 찾는 경우가 있어, 따옴표 속 검색어가 실제로 들어간 기사만 채택"""
    t = _ns(text)
    if any(w in text for w in qd.get('exclude', [])):     # 제외어는 띄어쓰기 그대로 비교('제12대 전반기'→'대전' 오인 방지)
        return False
    if qd.get('all'):
        return all(any(_ns(w) in t for w in grp) for grp in qd['all'])
    quoted = [] if qd.get('noquote') else re.findall(r'"([^"]+)"', qd['q'])
    if quoted and not any(_ns(p) in t for p in quoted):
        return False
    if qd.get('must') and not any(_ns(m) in t for m in qd['must']):
        return False
    return True


def norm(t):
    return re.sub(r'[\s\W_]+', '', t)[:40]


def month_windows(year, today):
    out = []
    for m in range(1, 13):
        a = f'{year}-{m:02d}-01'
        if a > today:
            break
        b = f'{year + (m == 12)}-{(m % 12) + 1:02d}-01'
        out.append((a, min(b, (datetime.strptime(today, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d'))))
    return out


def plan(issue=False):
    """(기관id, 검색조건) 목록. issue=True면 기관·부서 대표 검색어에 쟁점어를 붙인 검색도 추가"""
    out = [(uid, qd) for uid, qs in QUERIES.items() for qd in qs]
    if issue:
        for uid, qs in QUERIES.items():
            for qd in [x for x in qs if not x.get('all')][:2]:
                out.append((uid, dict(qd, q='(' + qd['q'] + ') ' + ISSUE_OR)))
    return out


def main(windows=None):
    global WINDOW
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, 'news.json')
    db = {'updated': None, 'runs': [], 'items': []}
    if os.path.exists(path):
        db = json.load(open(path, encoding='utf-8'))
    items = db['items']
    by_key = {norm(it['title']): it for it in items}

    now = datetime.now(KST)
    today = now.strftime('%Y-%m-%d')
    added = 0
    cutoff0 = (now - timedelta(days=(DAYS if not windows else 400))).strftime('%Y-%m-%d')
    jobs = [(None, plan(issue=True))] if not windows else [(w, plan(issue=True)) for w in windows]
    if ONLY:
        jobs = [(w, [(u, q) for u, q in pl if u in ONLY and (not ONLY_NEW or q.get('all'))]) for w, pl in jobs]
    for w, pl in jobs:
        WINDOW = w
        if w:
            print(f'── {w[0]} ~ {w[1]} ──', flush=True)
        for uid, qd in pl:
            for el in fetch(qd['q']):
                src = el.findtext('source') or ''
                title = clean_title(el.findtext('title'), src)
                desc = re.sub(r'<[^>]+>', ' ', html.unescape(el.findtext('description') or ''))
                text = title + ' ' + desc
                if not relevant(qd, text):
                    continue
                try:
                    pub = parsedate_to_datetime(el.findtext('pubDate')).astimezone(KST)
                except Exception:
                    pub = now
                k = norm(title)
                if not k:
                    continue
                it = by_key.get(k)
                if it is None:
                    it = {'title': title, 'source': src, 'url': el.findtext('link'),
                          'date': pub.strftime('%Y-%m-%d'), 'time': pub.strftime('%H:%M'),
                          'first_seen': today, 'units': [], 'tags': []}
                    it['tags'] = [n for n, rx in TAGS if re.search(rx, title)]
                    items.append(it)
                    by_key[k] = it
                    added += 1
                if uid not in it['units']:
                    it['units'].append(uid)
            time.sleep(0.8)
    WINDOW = None
    for uid in QUERIES:
        print(f'{uid:12s} 누적 {sum(1 for i in items if uid in i["units"])}건')

    # 태그 규칙이 바뀌어도 전체 기사에 똑같이 적용 + 제목에 기관명이 있으면 그 기관에도 연결
    for it in items:
        keep = ['보도자료'] if '보도자료' in it.get('tags', []) else []
        for uid, kws in TITLE_MAP.items():
            if uid not in it['units'] and any(k in it['title'] for k in kws) and not all(u.startswith('f-') for u in it['units']):
                it['units'].append(uid)
        it['tags'] = keep + [n for n, rx in TAGS if n != '보도자료' and re.search(rx, it['title'])]
        if windows:                      # 소급 수집분은 'NEW'로 표시되지 않도록 발행일을 최초 수집일로
            it['first_seen'] = min(it['first_seen'], it['date'])


    # 문체부 보도자료(누리집)
    if not ONLY:
        for title, url, date in fetch_mcst(2 if not windows else 5):
            if date and date < cutoff0:
                continue
            k = norm(title)
            if not k or k in by_key:
                if k in by_key and 'f-policy' not in by_key[k]['units']:
                    by_key[k]['units'].append('f-policy')
                continue
            it = {'title': title, 'source': '문화체육관광부', 'url': url, 'date': date or today, 'time': '09:00',
                  'first_seen': date if windows and date else today, 'units': ['f-policy'], 'tags': ['보도자료']}
            items.append(it)
            by_key[k] = it
            added += 1

    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    items[:] = [i for i in items if i['date'] >= cutoff]
    items.sort(key=lambda i: (i['date'], i['time']), reverse=True)
    db['updated'] = now.strftime('%Y-%m-%d %H:%M')
    run = {'at': db['updated'], 'added': added}
    if windows:
        run['note'] = f'소급 수집 {windows[0][0]} ~ {windows[-1][1]}'
    db['runs'] = ([run] + db.get('runs', []))[:60]
    json.dump(db, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(DATA, 'news_data.js'), 'w', encoding='utf-8') as f:
        f.write('window.NEWS = ' + json.dumps(db, ensure_ascii=False) + ';\n')
    print(f'\n완료: 새 기사 {added}건 / 전체 {len(items)}건 ({db["updated"]})')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if len(sys.argv) > 2:                             # 예) python 뉴스수집.py 2026 guk  → 해당 기관만
        ONLY = sys.argv[2].split(',')
        ONLY_NEW = '--council' in sys.argv
    if re.fullmatch(r'20\d\d', arg):                  # 예) python 뉴스수집.py 2026 → 그해 1월부터 월별 소급(쟁점 검색 포함)
        main(month_windows(int(arg), datetime.now(KST).strftime('%Y-%m-%d')))
    else:
        if arg.isdigit():                              # 예) python 뉴스수집.py 60  → 최근 60일 소급
            DAYS = int(arg)
        main()
