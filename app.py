"""제주대학교병원 의생명연구원 — 국가 R&D 공고 마감 대시보드 (Streamlit)."""
import io
import os
from datetime import date

import pandas as pd
import streamlit as st

import collector
import config
from sources import SOURCES
from store import Store, backend_from_env

st.set_page_config(page_title="의생명연구원 R&D 공고 대시보드", page_icon="📅", layout="wide")


# ── 선택: 접근 비밀번호 (환경변수 GRANT_APP_PASSWORD 설정 시에만 요구) ──
def _secrets():
    try:
        return dict(st.secrets)
    except Exception:
        return {}


SECRETS = _secrets()


def _gate():
    pw = SECRETS.get("APP_PASSWORD") or os.environ.get("GRANT_APP_PASSWORD")
    if not pw or st.session_state.get("authed"):
        return
    v = st.text_input("비밀번호", type="password")
    if v == pw:
        st.session_state.authed = True
        st.rerun()
    st.stop()


_gate()


@st.cache_resource(ttl=180, show_spinner="데이터 불러오는 중…")
def get_store():
    return Store(backend_from_env(SECRETS))


store = get_store()


def load() -> pd.DataFrame:
    df = store.df["notices"].copy()
    if df.empty:
        return df
    rv = store.reviews().drop(columns=["updated_by", "updated_at"])
    df = df.merge(rv, on="ancm_id", how="left")
    for c in ["review_status", "assignee", "memo", "end_override"]:
        df[c] = df[c].fillna("")
    df.loc[df["review_status"] == "", "review_status"] = "신규"
    today = pd.Timestamp(date.today())
    end = df["end_override"].where(df["end_override"].fillna("") != "", df["rcv_end"])
    df["마감일"] = pd.to_datetime(end.fillna("").str[:10], errors="coerce")
    df["추정"] = (df["end_estimated"].isin(["1", 1])) & (df["end_override"].fillna("") == "")
    df["D-day"] = (df["마감일"] - today).dt.days
    text = (df["title"].fillna("") + " " + df["body_text"].fillna(""))
    kw = "|".join(config.BIO_KEYWORDS)
    df["의생명"] = (df["ministry"].isin(config.BIO_MINISTRIES) | df["source"].isin(config.BIO_SOURCES)
                  | text.str.contains(kw, regex=True))
    df["비공모"] = df["title"].fillna("").str.contains("|".join(config.NON_CALL_KEYWORDS), regex=True)
    # 중복 공고(여러 출처에 같은 제목) 묶기: SOURCES 순서가 우선
    order = {n: i for i, (n, _) in enumerate(SOURCES)}
    df["_key"] = df["title"].fillna("").str.replace(r"[^0-9A-Za-z가-힣]", "", regex=True).str.replace(r"공고|안내|신규|지원|대상|과제", "", regex=True).str[:40]
    df["_ord"] = df["source"].map(order).fillna(99)
    df = df.sort_values("_ord")
    df["출처들"] = df.groupby("_key")["source"].transform(lambda x: " · ".join(dict.fromkeys(x)))
    df["중복"] = df.duplicated("_key", keep="first") & (df["_key"].str.len() >= 8)
    df["제주"] = text.str.contains("|".join(config.REGION_KEYWORDS), regex=True)
    return df


def dday_label(d):
    if pd.isna(d):
        return "미정"
    d = int(d)
    return "D-day" if d == 0 else (f"D-{d}" if d > 0 else f"마감({-d}일 전)")


# ── 사이드바 ──
with st.sidebar:
    st.header("수집")
    runs = store.last_runs()
    st.caption(f"저장소: {store.b.label}")
    if runs.empty:
        st.caption("수집 이력 없음")
    else:
        for _, r in runs.iterrows():
            flag = "⚠️" if r["error"] else "✅"
            st.caption(f"{flag} {r['source']} · {r['run_at'][5:16].replace('T', ' ')}")
    if st.button("🔄 새로고침", width="stretch"):
        get_store.clear()
        st.rerun()
    only_src = st.multiselect("수집할 출처", [n for n, _ in SOURCES], default=[n for n, _ in SOURCES])
    if st.button("지금 수집", width="stretch"):
        box = st.empty()
        logs = []
        try:
            with st.spinner("수집 중… (1~3분)"):
                summ = collector.collect(
                    store, only_src, log=lambda m: (logs.append(m), box.code("\n".join(logs[-8:]))))
            st.success(" / ".join(f"{k} 신규 {a}" for k, (a, b, e) in summ.items() if not e) or "완료")
            for k, (a, b, e) in summ.items():
                if e:
                    st.error(f"{k} 실패: {e}")
            st.caption("해외 서버에서 차단되는 사이트는 GitHub Actions/원내 PC 수집을 이용하세요 (README).")
        except Exception as e:
            st.error(f"수집 실패: {e}")

    st.header("필터")
    df_all = load()
    if df_all.empty:
        st.info("아직 데이터가 없습니다. 위 버튼으로 수집하세요.")
        st.stop()
    only_bio = st.toggle("의생명 관련만", value=True)
    hide_noncall = st.toggle("결과·행정 공지 숨기기", value=True)
    hide_dup = st.toggle("중복 공고 합치기", value=True, help="IRIS·연구재단·HT Dream 등에 같은 공고가 있으면 하나만 표시")
    only_jeju = st.toggle("제주 관련만", value=False)
    hide_closed = st.toggle("마감 공고 숨기기", value=True)
    srcs = st.multiselect("출처", [n for n, _ in SOURCES])
    ministries = st.multiselect("소관부처", sorted(df_all["ministry"].dropna().unique()))
    rv = st.multiselect("검토 상태", config.REVIEW_STATUSES,
                        default=[s for s in config.REVIEW_STATUSES if s != "제외"])
    q = st.text_input("검색 (공고명·공고문)")

df = df_all.copy()
if only_bio:
    df = df[df["의생명"]]
if only_jeju:
    df = df[df["제주"]]
if hide_closed:
    df = df[~(df["D-day"] < 0)]
if hide_noncall:
    df = df[~df["비공모"]]
if hide_dup and not srcs:
    df = df[~df["중복"]]
if srcs:
    df = df[df["source"].isin(srcs)]
if ministries:
    df = df[df["ministry"].isin(ministries)]
if rv:
    df = df[df["review_status"].isin(rv)]
if q:
    df = df[(df["title"].fillna("") + df["body_text"].fillna("")).str.contains(q, case=False, regex=False)]
df = df.sort_values(["D-day", "posted"], na_position="last")

# ── 헤더 & KPI ──
st.title("📅 의생명연구원 국가 R&D 공고 대시보드")
st.caption("출처: IRIS · 한국연구재단 · HT Dream · KHIDI · NECA · 환경부(KEITI) · 필터 적용 기준 · "
           "마감일 옆 *는 공고문에서 자동 추정한 값(확인 필요)")
open_df = df[df["D-day"].fillna(9999) >= 0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("진행 중 공고", len(open_df))
c2.metric(f"{config.URGENT_DAYS}일 내 마감", int((open_df["D-day"] <= config.URGENT_DAYS).sum()))
c3.metric("미검토(신규)", int((df["review_status"] == "신규").sum()))
c4.metric("안내완료·지원예정", int(df["review_status"].isin(["연구자 안내완료", "지원 예정"]).sum()))

tab1, tab2, tab3, tab4 = st.tabs(["⏰ 마감 임박", "📋 공고 관리", "🗓 마감 달력", "🔎 공고 상세"])

# ── 탭1: 마감 임박 ──
with tab1:
    groups = [
        (f"🔴 {config.URGENT_DAYS}일 이내", open_df[open_df["D-day"] <= config.URGENT_DAYS]),
        (f"🟠 {config.SOON_DAYS}일 이내", open_df[(open_df["D-day"] > config.URGENT_DAYS) & (open_df["D-day"] <= config.SOON_DAYS)]),
        ("🟢 그 이후 / 마감일 미정", open_df[~(open_df["D-day"] <= config.SOON_DAYS)]),
    ]
    for label, g in groups:
        st.subheader(f"{label} · {len(g)}건")
        if g.empty:
            st.caption("해당 없음")
            continue
        for _, r in g.iterrows():
            tag = " 🏝️" if r["제주"] else ""
            who = f" · 담당: {r['assignee']}" if r["assignee"] else ""
            est = "*" if r["추정"] else ""
            end_s = r["마감일"].strftime("%Y-%m-%d") if pd.notna(r["마감일"]) else "?"
            st.markdown(
                f"**{dday_label(r['D-day'])}{est}** &nbsp; [{r['title']}]({r['url']}){tag}  \n"
                f"<span style='color:gray;font-size:0.85em'>{r['출처들']} · {r['ministry'] or ''} {r['agency'] or ''} · "
                f"접수 {r['rcv_start'] or '?'} ~ {end_s}{est} · [{r['review_status']}]{who}</span>",
                unsafe_allow_html=True)

# ── 탭2: 공고 관리 (담당자 입력) ──
with tab2:
    st.caption("검토 상태·담당 연구자·메모를 수정한 뒤 **저장**을 누르세요. 재수집해도 입력 내용은 유지됩니다.")
    user = st.text_input("수정자 이름", key="editor_name")
    view = df[["ancm_id", "D-day", "title", "출처들", "agency", "rcv_end", "추정", "url",
               "end_override", "review_status", "assignee", "memo"]].copy()
    view["D-day"] = view["D-day"].map(dday_label)
    view = view.set_index("ancm_id")
    edited = st.data_editor(
        view, hide_index=True, width="stretch", height=520,
        disabled=["D-day", "title", "출처들", "agency", "rcv_end", "추정", "url"],
        column_config={
            "title": st.column_config.TextColumn("공고명", width="large"),
            "출처들": "출처", "agency": "기관", "rcv_end": "마감일(수집)",
            "추정": st.column_config.CheckboxColumn("추정", help="공고문에서 자동 추정 — 확인 후 '마감일 수정'에 입력"),
            "url": st.column_config.LinkColumn("원문", display_text="열기"),
            "end_override": st.column_config.TextColumn("마감일 수정", help="YYYY-MM-DD"),
            "review_status": st.column_config.SelectboxColumn("검토 상태", options=config.REVIEW_STATUSES, required=True),
            "assignee": st.column_config.TextColumn("담당 연구자"),
            "memo": st.column_config.TextColumn("메모", width="medium"),
        }, key="editor")
    colA, colB = st.columns([1, 1])
    if colA.button("💾 저장", type="primary"):
        cols = ["review_status", "assignee", "memo", "end_override"]
        changes = {aid: {c: (r[c] or "").strip() for c in cols}
                   for aid, r in edited.iterrows()
                   if any((view.loc[aid, c] or "") != (r[c] or "") for c in cols)}
        try:
            n = store.save_reviews(changes, user)
            st.toast(f"{n}건 저장")
            st.rerun()
        except Exception as e:
            st.error(f"저장 실패: {e}")

    out = df[["D-day", "title", "출처들", "ministry", "agency", "rcv_start", "마감일", "추정",
              "contact", "url", "review_status", "assignee", "memo"]].copy()
    out["D-day"] = out["D-day"].map(dday_label)
    out["마감일"] = out["마감일"].dt.strftime("%Y-%m-%d")
    out["추정"] = out["추정"].map({True: "추정", False: ""})
    out.columns = ["D-day", "공고명", "출처", "소관부처", "기관", "접수시작", "접수마감", "마감일 추정여부",
                   "사업담당자", "원문 링크", "검토상태", "담당연구자", "메모"]
    buf = io.BytesIO()
    out.to_excel(buf, index=False, sheet_name="공고목록")
    colB.download_button("⬇️ 엑셀로 내보내기 (연구자 안내용)", buf.getvalue(),
                         file_name=f"RD공고_{date.today():%Y%m%d}.xlsx",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── 탭3: 마감 달력 ──
with tab3:
    cal = open_df.dropna(subset=["마감일"]).copy()
    if cal.empty:
        st.caption("마감일이 있는 공고가 없습니다.")
    else:
        cal["주"] = cal["마감일"].dt.to_period("W-SUN").dt.start_time.dt.strftime("%m/%d 주")
        wk = cal.groupby("주", sort=False).size()
        st.subheader("주별 마감 건수")
        st.bar_chart(wk.sort_index())
        st.subheader("날짜별 목록")
        for d, g in cal.sort_values("마감일").groupby(cal["마감일"].dt.date, sort=True):
            with st.expander(f"{d:%Y-%m-%d (%a)} · {len(g)}건 · {dday_label(g['D-day'].iloc[0])}"):
                for _, r in g.iterrows():
                    st.markdown(f"- [{r['title']}]({r['url']}){'*' if r['추정'] else ''} — {r['출처들']} [{r['review_status']}]")

# ── 탭4: 공고 상세 ──
with tab4:
    if df.empty:
        st.caption("공고 없음")
    else:
        opts = {f"{dday_label(r['D-day'])} | {r['title']}": r["ancm_id"] for _, r in df.iterrows()}
        pick = st.selectbox("공고 선택", list(opts))
        r = df[df["ancm_id"] == opts[pick]].iloc[0]
        st.subheader(r["title"])
        a, b = st.columns(2)
        a.markdown(f"**출처** {r['출처들']}  \n**소관부처** {r['ministry']}  \n**기관** {r['agency']}  \n"
                   f"**사업** {r['program'] or '-'}  \n**공고번호** {r['ancm_no'] or '-'}  \n**분류** {r['category'] or '-'}")
        end_s = r["마감일"].strftime("%Y-%m-%d") if pd.notna(r["마감일"]) else "미정"
        b.markdown(f"**접수기간** {r['rcv_start'] or '?'} ~ {end_s}{' (공고문에서 추정 — 확인 필요)' if r['추정'] else ''}  \n"
                   f"**게시일** {r['posted'] or '-'}  \n**사업담당자** {r['contact'] or '-'}  \n**상태** {r['status'] or '-'}")
        note = " (IRIS·HT Dream은 상세 주소가 없어 목록으로 이동합니다 — 공고명으로 검색)" if r["source"] in ("IRIS", "HT Dream") else ""
        st.markdown(f"[원문 열기]({r['url']}){note}")
        st.text_area("공고문", r["body_text"] or "(수집된 본문 없음)", height=300)
