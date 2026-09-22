# -*- coding: utf-8 -*-
"""
쟁점 보도 → 기관·부서별 「주요 이슈」·「질의 착안점」 반영
 - 입력: data/_issue_patch.json  (매일 예약작업에서 Claude가 새 쟁점 기사를 검토해 작성)
 - 출력: data/units_data.js 갱신 + data/issue_log.js 에 이력 추가
 - 안전장치: 기관 id·이슈 id 확인, 기사 링크는 data/news.json 에 실제로 있는 것만 허용,
            저장 전 백업(data/backup/units_data_날짜.js)

패치 형식
{
 "date": "2026-09-19",
 "changes": [
  {"unit": "a-ggac", "action": "new",
   "issue": {"level": "high", "title": "...", "detail": "...", "src": "2026.9.19 보도"},
   "links": ["https://news.google.com/rss/articles/..."],
   "point": "질의 착안점(선택)"},
  {"unit": "a-ggac", "action": "update", "issue_id": "a-ggac-1",
   "detail": "내용 보강(선택, 없으면 유지)", "level": "high(선택)", "src": "(선택)",
   "links": ["..."], "point": "(선택)"},
  {"unit": "a-ggac", "action": "qa", "qa_summary": "쟁점 요약 교체(선택)"}
 ]
}
별도 항목(기관과 무관한 분야·정부·타 시도 자료, 행감 의제)은 changes 대신 아래 키로 넣는다(모두 선택, 추가·보강만 하며 기존 항목을 지우지 않는다).
 "bench": [ {"action":"new","id":"B14","topic":"주제","units":["d-arts"],"gov":["정부 내용"],"other":[{"r":"서울","t":"내용"}],
             "gg":"경기도 현황","impl":"시사점","src":[{"t":"기사 제목","url":"주소","src":"매체 2026.9.21"}]},
            {"action":"update","id":"B3","gov":["추가할 내용"],"other":[...],"gg":"(교체, 선택)","impl":"(교체, 선택)","src":[...]} ],
 "agenda": [ {"action":"new","title":"의제명","why":"이유","units":["guk"],"qrefs":["guk:1"],"bench":["B14"],"how":"진행 방법"},
             {"action":"update","rank":3,"why":"(교체, 선택)","qrefs":[...],"bench":[...],"how":"(교체, 선택)"} ]

new·update·qa 어느 변경에든 아래를 덧붙이면 「질의·자료요구」(data/qa_data.js)도 함께 갱신된다(모두 선택).
   "question": {"pri": "상|중", "topic": "...", "q": "질의문", "bg": "배경", "findings": ["처리-3"], "reqs": ["공통-6"]},
   "request":  {"title": "자료명", "items": ["세부 항목", ...]},
   "qa_summary": "해당 기관 쟁점 요약 전체 문장(교체)"
"""
import json, os, sys, shutil
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')
UNITS_JS = os.path.join(DATA, 'units_data.js')
LOG_JS = os.path.join(DATA, 'issue_log.js')
PATCH = os.path.join(DATA, '_issue_patch.json')
MARK = '\nwindow.UNITS = '
QA_JS = os.path.join(DATA, 'qa_data.js')
QMARK = '\nwindow.QA = '


def load_units():
    t = open(UNITS_JS, encoding='utf-8').read()
    head, body = t.split(MARK, 1)
    return head, json.loads(body.rstrip().rstrip(';'))


def load_log():
    if not os.path.exists(LOG_JS):
        return []
    t = open(LOG_JS, encoding='utf-8').read()
    return json.loads(t.split('window.ISSUE_LOG = ', 1)[1].rstrip().rstrip(';'))


def main():
    if not os.path.exists(PATCH):
        print('반영할 패치 없음(data/_issue_patch.json)')
        return
    patch = json.load(open(PATCH, encoding='utf-8'))
    date = patch.get('date') or datetime.now().strftime('%Y-%m-%d')
    news = {i['url']: i for i in json.load(open(os.path.join(DATA, 'news.json'), encoding='utf-8'))['items']}
    head, d = load_units()
    U = {u['id']: u for u in d['units']}
    qt = open(QA_JS, encoding='utf-8').read()
    qhead, qbody = qt.split(QMARK, 1)
    QA = json.loads(qbody.rstrip().rstrip(';'))
    allreq = {r['no'] for r in QA['common']} | {r['no'] for v in QA['units'].values() for r in v['requests']}
    qa_changed = []
    log, errors = [], []

    # ── 공통 자료요구 추가 ──
    for c in patch.get('common', []):
        if not c.get('title') or not isinstance(c.get('items'), list):
            errors.append('공통 자료요구 형식 오류: title·items 필요')
            continue
        if any(r['title'] == c['title'] for r in QA['common']):
            errors.append(f"이미 있는 공통 자료요구: {c['title']}")
            continue
        no = f"공통-{len(QA['common']) + 1}"
        QA['common'].append({'no': no, 'title': c['title'], 'items': c['items'], 'why': c.get('why', ''), 'qs': [],
                             'auto': True, 'added': date})
        allreq.add(no)
        qa_changed.append(f"공통 자료요구 {no} {c['title']}")

    def links_of(urls):
        out = []
        for url in urls or []:
            it = news.get(url)
            if not it:
                errors.append(f'수집 목록에 없는 링크 제외: {url[:80]}')
                continue
            out.append({'title': it['title'], 'source': it['source'], 'date': it['date'], 'url': url})
        return out

    for c in patch.get('changes', []):
        u = U.get(c.get('unit'))
        if not u:
            errors.append(f"없는 기관 id: {c.get('unit')}")
            continue
        links = links_of(c.get('links'))
        if c.get('action') == 'new':
            iss = c.get('issue') or {}
            if not iss.get('title') or iss.get('level') not in ('high', 'mid', 'low'):
                errors.append(f"새 이슈 형식 오류({u['id']}): 제목·수준(high/mid/low) 필요")
                continue
            n = 1 + max([int(i['id'].rsplit('-', 1)[1]) for i in u['issues'] if i.get('id', '').rsplit('-', 1)[-1].isdigit()] or [0])
            new = {'id': f"{u['id']}-{n}", 'level': iss['level'], 'title': iss['title'], 'detail': iss.get('detail', ''),
                   'src': iss.get('src', ''), 'links': links, 'added': date, 'updated': date, 'auto': True}
            u['issues'].insert(0, new)
            log.append({'date': date, 'unit': u['id'], 'action': '신규', 'issue_id': new['id'], 'title': new['title'], 'n_links': len(links)})
            target = new
        elif c.get('action') == 'qa':
            target = None
        elif c.get('action') == 'update':
            target = next((i for i in u['issues'] if i.get('id') == c.get('issue_id')), None)
            if not target:
                errors.append(f"없는 이슈 id: {c.get('issue_id')}")
                continue
            for k in ('detail', 'level', 'src', 'title'):
                if c.get(k):
                    target[k] = c[k]
            have = {l['url'] for l in target.get('links', [])}
            target.setdefault('links', []).extend(l for l in links if l['url'] not in have)
            target['links'].sort(key=lambda l: l['date'], reverse=True)
            target['updated'] = date
            # 갱신된 이슈는 목록 맨 위로
            u['issues'].remove(target)
            u['issues'].insert(0, target)
            log.append({'date': date, 'unit': u['id'], 'action': '갱신', 'issue_id': target['id'], 'title': target['title'], 'n_links': len(links)})
        else:
            errors.append(f"알 수 없는 action: {c.get('action')}")
            continue
        if c.get('point') and c['point'] not in u['points']:
            u['points'].append(c['point'])     # 끝에 추가(기존 체크 표시가 밀리지 않도록)

        # ── 질의·자료요구 반영 ──
        qa = QA['units'].get(u['id'])
        if qa is not None:
            new_req = None
            rq = c.get('request')
            if rq:
                if not rq.get('title') or not isinstance(rq.get('items'), list):
                    errors.append(f"자료요구 형식 오류({u['id']}): title·items 필요")
                else:
                    new_req = f"{qa['prefix']}-{len(qa['requests']) + 1}"
                    qa['requests'].append({'no': new_req, 'title': rq['title'], 'items': rq['items'], 'why': rq.get('why', ''),
                                           'qs': [], 'auto': True, 'added': date})
                    allreq.add(new_req)
                    qa_changed.append(f"{u['id']} 자료요구 {new_req} {rq['title']}")
            qq = c.get('question')
            if qq:
                if qq.get('pri') not in ('상', '중') or not qq.get('q') or not qq.get('topic'):
                    errors.append(f"질의 형식 오류({u['id']}): pri(상/중)·topic·q 필요")
                else:
                    reqs = ([new_req] if new_req else []) + [r for r in qq.get('reqs', []) if r in allreq]
                    bad = [r for r in qq.get('reqs', []) if r not in allreq]
                    if bad:
                        errors.append(f"없는 자료요구 번호 제외: {bad}")
                    fnos = {f"{f['type']}-{f['no']}" for f in u['findings']}
                    no = len(qa['questions']) + 1
                    qa['questions'].append({'no': no, 'pri': qq['pri'], 'topic': qq['topic'], 'q': qq['q'], 'bg': qq.get('bg', ''),
                                            'issues': [target['id']] if target else [], 'findings': [x for x in qq.get('findings', []) if x in fnos],
                                            'reqs': reqs, 'bench': [b for b in qq.get('bench', []) if b in {x['id'] for x in QA.get('bench', [])}],
                                            'auto': True, 'added': date})
                    if new_req:
                        qa['requests'][-1]['qs'] = [no]
                    qa_changed.append(f"{u['id']} 질의 {no} {qq['topic']}")
            if c.get('qa_summary'):
                qa['summary'] = c['qa_summary']
                qa_changed.append(f"{u['id']} 쟁점 요약 갱신")
            if c.get('action') == 'qa' and not (rq or qq or c.get('qa_summary')):
                errors.append(f"qa 변경에 내용 없음({u['id']})")

    # 오늘 반영된 이슈를 위로(중요→주의→참고 순), 나머지는 기존 순서 유지
    rank = {'high': 0, 'mid': 1, 'low': 2}
    for u in d['units']:
        u['issues'].sort(key=lambda i: (0, rank.get(i['level'], 3)) if i.get('updated') == date else (1, 0))

    # ── 정부·타 시도(bench) ──
    BK = {b['id']: b for b in QA.get('bench', [])}
    for c in patch.get('bench', []):
        if c.get('action') == 'new':
            bid = c.get('id') or 'B' + str(len(QA['bench']) + 1)
            if bid in BK:
                errors.append(f'이미 있는 비교 id: {bid}')
                continue
            if not c.get('topic') or not c.get('impl'):
                errors.append('비교 형식 오류: topic·impl 필요')
                continue
            b = {'id': bid, 'topic': c['topic'], 'units': [u for u in c.get('units', []) if u in U],
                 'gov': c.get('gov', []), 'other': c.get('other', []), 'gg': c.get('gg', ''), 'impl': c['impl'],
                 'src': c.get('src', []), 'added': date, 'auto': True}
            QA.setdefault('bench', []).append(b)
            BK[bid] = b
            qa_changed.append(f"정부·타시도 {bid} {c['topic']}")
        elif c.get('action') == 'update':
            b = BK.get(c.get('id'))
            if not b:
                errors.append(f"없는 비교 id: {c.get('id')}")
                continue
            for k in ('gov', 'src'):
                have = [json.dumps(x, ensure_ascii=False) for x in b.get(k, [])]
                for x in c.get(k, []):
                    if json.dumps(x, ensure_ascii=False) not in have:
                        b.setdefault(k, []).append(x)
            for x in c.get('other', []):
                if x not in b.get('other', []):
                    b.setdefault('other', []).append(x)
            for k in ('gg', 'impl', 'topic'):
                if c.get(k):
                    b[k] = c[k]
            for u in c.get('units', []):
                if u in U and u not in b['units']:
                    b['units'].append(u)
            b['updated'] = date
            qa_changed.append(f"정부·타시도 {b['id']} 보강")
        else:
            errors.append('bench: action 은 new 또는 update')

    # ── 행감 의제(agenda) ──
    for c in patch.get('agenda', []):
        if c.get('action') == 'new':
            if not c.get('title') or not c.get('why'):
                errors.append('의제 형식 오류: title·why 필요')
                continue
            rank = max([a['rank'] for a in QA.get('agenda', [])] or [0]) + 1
            QA.setdefault('agenda', []).append({'rank': rank, 'title': c['title'], 'why': c['why'],
                'units': [u for u in c.get('units', []) if u in U], 'qrefs': c.get('qrefs', []),
                'bench': [b for b in c.get('bench', []) if b in BK], 'how': c.get('how', ''), 'added': date, 'auto': True})
            qa_changed.append(f"행감 의제 {rank}. {c['title']}")
        elif c.get('action') == 'update':
            a = next((x for x in QA.get('agenda', []) if x['rank'] == c.get('rank')), None)
            if not a:
                errors.append(f"없는 의제 순번: {c.get('rank')}")
                continue
            for k in ('why', 'how', 'title'):
                if c.get(k):
                    a[k] = c[k]
            for k in ('units', 'qrefs', 'bench'):
                for x in c.get(k, []):
                    if x not in a.get(k, []):
                        a.setdefault(k, []).append(x)
            a['updated'] = date
            qa_changed.append(f"행감 의제 {a['rank']} 보강")
        else:
            errors.append('agenda: action 은 new 또는 update')

    if qa_changed:
        os.makedirs(os.path.join(DATA, 'backup'), exist_ok=True)
        shutil.copy(QA_JS, os.path.join(DATA, 'backup', f"qa_data_{datetime.now().strftime('%Y%m%d_%H%M')}.js"))
        QA['updated'] = date
        QA['log'].insert(0, {'date': date, 'note': '자동 반영: ' + '; '.join(qa_changed)[:300]})
        text = qhead + QMARK + json.dumps(QA, ensure_ascii=False, indent=1) + ';\n'
        json.loads(text.split(QMARK, 1)[1].rstrip().rstrip(';'))
        open(QA_JS, 'w', encoding='utf-8').write(text)

    if log:
        os.makedirs(os.path.join(DATA, 'backup'), exist_ok=True)
        shutil.copy(UNITS_JS, os.path.join(DATA, 'backup', f"units_data_{datetime.now().strftime('%Y%m%d_%H%M')}.js"))
        text = head + MARK + json.dumps(d, ensure_ascii=False, indent=1) + ';\n'
        json.loads(text.split(MARK, 1)[1].rstrip().rstrip(';'))          # 저장 전 형식 재확인
        open(UNITS_JS, 'w', encoding='utf-8').write(text)
        all_log = (log + load_log())[:500]
        open(LOG_JS, 'w', encoding='utf-8').write('window.ISSUE_LOG = ' + json.dumps(all_log, ensure_ascii=False) + ';\n')

    os.replace(PATCH, os.path.join(DATA, 'backup', f"_issue_patch_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
               if os.path.isdir(os.path.join(DATA, 'backup')) else PATCH + '.done')
    for l in log:
        print(f"[{l['action']}] {l['unit']} {l['issue_id']} {l['title']} (+링크 {l['n_links']})")
    for q in qa_changed:
        print('[질의·자료요구] ' + q)
    for e in errors:
        print('  ! ' + e)
    print(f'완료: 반영 {len(log)}건, 경고 {len(errors)}건')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    main()
