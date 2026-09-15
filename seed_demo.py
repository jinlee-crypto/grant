"""사이트 접속 없이 화면 확인용 예시 데이터 (demo_data/). 실제 운영에는 쓰지 마세요.
사용: python seed_demo.py  →  GRANT_DATA=demo_data streamlit run app.py"""
import os
from datetime import date, timedelta
os.environ.setdefault("GRANT_DATA", "demo_data")
from store import Store, LocalFiles
t = date.today()
D = lambda n: str(t + timedelta(days=n))
rows = [
 ("IRIS", "1", "2026년도 제4차 첨단재생의료 임상연구 활성화 지원 사업 신규과제 공고", "보건복지부", "한국보건산업진흥원", 3, 0),
 ("HT Dream", "2", "2026년도 제4차 첨단재생의료 임상연구 활성화 지원 사업 신규과제 공고 안내", "보건복지부", "한국보건산업진흥원", 3, 0),
 ("IRIS", "3", "2026년 4극3특 제주특별자치도 과학기술혁신지원사업 연구단 모집 공고", "과학기술정보통신부", "연구개발특구진흥재단", 12, 0),
 ("한국연구재단", "4", "2026년도 국가과학자지원사업(리더급 국가과학기술자) 공모", "과학기술정보통신부", "한국연구재단", 27, 0),
 ("KHIDI", "5", "2026년 글로벌 규제 대응 비용 지원(의료기기) 사업 수행기업 모집 3차 공고", "보건복지부", "한국보건산업진흥원", 13, 1),
 ("NECA", "6", "「2026년 선진입 의료기술 임상연구 지원 시범사업」 신청 공고", "보건복지부", "한국보건의료연구원", 20, 1),
 ("NECA", "7", "2026년 한국보건의료연구원 제2차 원탁회의 개최 안내", "보건복지부", "한국보건의료연구원", None, 0),
 ("환경부(KEITI)", "8", "2027년 환경기술개발사업 신규과제 공고(환경보건)", "환경부", "한국환경산업기술원", 40, 1),
]
s = Store(LocalFiles(os.environ["GRANT_DATA"]))
for src, i, ti, mi, ag, dd, est in rows:
    s.upsert(dict(ancm_id=f"{src}:{i}", source=src, title=ti, ministry=mi, agency=ag, posted=D(-5),
                  rcv_start=D(-2) if dd else "", rcv_end=D(dd) if dd else "", end_estimated=est,
                  contact="담당자(000-0000)", url="https://example.org", body_text=ti + " 공고문 예시"))
s.log_run("IRIS", len(rows), 0)
s.save_collected()
print("demo_data/ 생성")
