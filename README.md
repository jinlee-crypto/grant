# 의생명연구원 국가 R&D 공고 대시보드

6개 출처의 공고를 모아 마감일 순으로 보여주고, 검토 상태·담당 연구자·메모를 함께 관리하는 Streamlit 앱.

| 출처 | 수집 위치 | 마감일 |
|---|---|---|
| IRIS | 사업공고(접수예정·접수중) | 접수기간 필드 |
| 한국연구재단 | 신규사업공모(최근 3개월 등록) | 접수일자 필드 |
| HT Dream | 사업공고(최근 2페이지) | 공고기간 필드 |
| KHIDI | 사업공고 게시판 | 제목·본문에서 **추정** (`*`) |
| NECA | 공지사항 + 입찰공고(연구용역) | 제목·본문에서 **추정** (`*`) |
| 환경부(KEITI) | 공지/공고 > R&D | 제목·본문에서 **추정** (`*`) |

## 구조: 코드는 `main`, 데이터는 `data` 브랜치
```
GitHub Actions (매일 07:00, 평일 13:00 KST) ──수집──▶ data 브랜치 / data/notices.csv, runs.csv
Streamlit 앱 ──읽기────────────────────────────────▶ data 브랜치 (GitHub API)
Streamlit 앱 ──검토 입력 저장(커밋)────────────────▶ data 브랜치 / data/reviews.csv
```
데이터 커밋이 `main`에 쌓이지 않으므로 앱이 저장할 때마다 재시작되지 않고, Streamlit 서버가 재시작돼도 데이터가 남습니다.

## 배포 (처음 한 번)
1. **GitHub 저장소 만들기** — *Private* 권장. 이 폴더 내용을 `main`에 올림.
2. **Actions 한 번 실행** — Actions 탭 → "공고 수집" → *Run workflow*. `data` 브랜치가 자동 생성되고 첫 수집이 들어갑니다.
   - 로그에서 출처별 `신규 N` 확인. `실패`가 나오면 아래 "수집이 막힐 때" 참고.
3. **토큰 발급** — GitHub → Settings → Developer settings → *Fine-grained tokens*
   → Repository access: 이 저장소만 → Permissions: **Contents: Read and write**.
4. **Streamlit Community Cloud** — New app → 저장소 / 브랜치 `main` / 파일 `app.py`
   → Advanced settings → Secrets 에 `.streamlit/secrets.toml.example` 내용을 채워 붙여넣기.
5. **보는 사람 제한** — 앱 Settings → Sharing 에서 이메일로 초대 (private 저장소 앱은 초대된 사람만 접근) [CHECK: 요금제별 private 앱 개수 제한은 Streamlit 문서에서 확인]. `APP_PASSWORD`를 넣으면 비밀번호도 한 번 더 묻습니다.

## 수집이 막힐 때
GitHub Actions·Streamlit 서버는 해외에 있어서, 일부 공공기관 사이트가 해외 접속을 막으면 그 출처만 `실패`로 뜹니다(나머지는 정상 수집).
그럴 땐 원내 PC에서 수집해 올립니다:
```
git clone <저장소> && cd <저장소>
pip install -r requirements.txt
collect_and_push.bat        # data 브랜치에 수집 결과 커밋·푸시
```
Windows 작업 스케줄러에 `collect_and_push.bat`을 매일 등록하면 자동화됩니다. 특정 출처만: `python collector.py --only KHIDI NECA`

## 로컬에서 화면 확인
```
python seed_demo.py
set GRANT_DATA=demo_data        (mac/linux: export GRANT_DATA=demo_data)
streamlit run app.py
```
Secrets가 없으면 로컬 `data/` 폴더를 사용합니다 (사이드바에 "저장소: 로컬 파일" 표시).

## 설정 — `config.py`
- '의생명 관련' 판정 부처·출처·키워드 / 숨길 결과·행정 공지 키워드 / 검토 상태 / 마감 임박 기준일

## 파일
```
app.py              대시보드 (마감 임박 / 공고 관리 / 마감 달력 / 공고 상세)
collector.py        수집 실행
store.py            CSV 저장소 (로컬 파일 또는 GitHub API), 저장 충돌 시 자동 병합
sources/            출처별 수집기 (iris, nrf, htdream, board=KHIDI·NECA·KEITI)
tests/              python -m pytest tests
.github/workflows/  자동 수집
```

## 유지보수
- 사이트 개편 시 해당 `sources/*.py`만 수정. `pytest`의 파서 테스트가 먼저 깨집니다.
- 요청 간 0.7초 간격, 상세 페이지는 새 공고만 조회. 마감 후 120일 지난 공고는 자동 정리.
- 추정 마감일(`*`)은 공고 관리 탭 "마감일 수정"에 확인값을 넣으면 그 값이 우선합니다.
