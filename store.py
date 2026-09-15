"""데이터 저장소 — CSV 3개(data/notices.csv, data/reviews.csv, data/runs.csv).

- 로컬/GitHub Actions: 저장소 폴더의 파일을 직접 읽고 씀 (LocalFiles)
- Streamlit Cloud: GitHub Contents API로 읽고 커밋 (GitHubFiles) → 재시작해도 데이터 유지
  st.secrets 또는 환경변수에 GITHUB_TOKEN, GITHUB_REPO("owner/repo") 가 있으면 자동 사용
"""
import base64
import io
import os
from datetime import datetime, timedelta

import pandas as pd
import requests

DATA_DIR = os.environ.get("GRANT_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))

NOTICE_COLS = ["ancm_id", "source", "title", "ministry", "agency", "program", "ancm_no", "posted",
               "category", "status", "rcv_start", "rcv_end", "end_estimated", "contact", "url",
               "body_text", "first_seen", "last_seen"]
REVIEW_COLS = ["ancm_id", "review_status", "assignee", "memo", "end_override", "updated_by", "updated_at"]
RUN_COLS = ["run_at", "source", "n_new", "n_updated", "error"]
FILES = {"notices": NOTICE_COLS, "reviews": REVIEW_COLS, "runs": RUN_COLS}
BODY_MAX = 6000        # CSV 크기 관리
KEEP_DAYS = 120        # 마감 후 이 기간이 지난 공고는 정리


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _empty(name):
    return pd.DataFrame(columns=FILES[name], dtype=str)


def _parse(text, name):
    if not text:
        return _empty(name)
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    for c in FILES[name]:
        if c not in df:
            df[c] = ""
    return df[FILES[name]]


# ── 백엔드 ──────────────────────────────────────────────
class LocalFiles:
    label = "로컬 파일"

    def __init__(self, root=DATA_DIR):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def read(self, name):
        p = os.path.join(self.root, f"{name}.csv")
        return (open(p, encoding="utf-8").read() if os.path.exists(p) else ""), None

    def write(self, name, text, sha, message):
        with open(os.path.join(self.root, f"{name}.csv"), "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return None


class Conflict(Exception):
    pass


class GitHubFiles:
    label = "GitHub"

    def __init__(self, repo, token, branch="main", path="data"):
        self.api = f"https://api.github.com/repos/{repo}/contents/{path}"
        self.branch = branch
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                  "X-GitHub-Api-Version": "2022-11-28"}

    def read(self, name):
        url = f"{self.api}/{name}.csv"
        meta = requests.get(url, headers=self.h, params={"ref": self.branch}, timeout=30)
        if meta.status_code == 404:
            return "", None
        meta.raise_for_status()
        sha = meta.json()["sha"]
        raw = requests.get(url, headers={**self.h, "Accept": "application/vnd.github.raw"},
                           params={"ref": self.branch}, timeout=60)
        raw.raise_for_status()
        return raw.content.decode("utf-8"), sha

    def write(self, name, text, sha, message):
        body = {"message": message, "branch": self.branch,
                "content": base64.b64encode(text.encode("utf-8")).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(f"{self.api}/{name}.csv", headers=self.h, json=body, timeout=60)
        if r.status_code in (409, 422) and "sha" in r.text:
            raise Conflict(r.text[:200])
        r.raise_for_status()
        return r.json()["content"]["sha"]


def backend_from_env(secrets=None):
    get = lambda k: (secrets.get(k) if secrets is not None and k in secrets else None) or os.environ.get(k)
    repo, token = get("GITHUB_REPO"), get("GITHUB_TOKEN")
    if repo and token:
        return GitHubFiles(repo, token, get("GITHUB_BRANCH") or "data")
    return LocalFiles()


# ── 저장소 ──────────────────────────────────────────────
class Store:
    def __init__(self, backend=None):
        self.b = backend or LocalFiles()
        self.df, self.sha = {}, {}
        for n in FILES:
            self._load(n)
        self._index()

    def _load(self, name):
        text, sha = self.b.read(name)
        self.df[name], self.sha[name] = _parse(text, name), sha

    def _index(self):
        self._pos = {a: i for i, a in enumerate(self.df["notices"]["ancm_id"])}
        self._new_rows = []

    # 수집용
    def known(self, ancm_id):
        i = self._pos.get(ancm_id)
        return None if i is None else self.df["notices"].iloc[i].to_dict()

    def upsert(self, it):
        now = _now()
        rec = {c: ("" if it.get(c) is None else str(it.get(c))) for c in NOTICE_COLS if c in it}
        if "body_text" in rec:
            rec["body_text"] = rec["body_text"][:BODY_MAX]
        i = self._pos.get(it["ancm_id"])
        if i is None:
            row = {c: "" for c in NOTICE_COLS}
            row.update(rec, first_seen=now, last_seen=now)
            self._pos[it["ancm_id"]] = len(self.df["notices"]) + len(self._new_rows)
            self._new_rows.append(row)
            return True
        if i >= len(self.df["notices"]):          # 같은 실행에서 새로 추가된 행
            row = self._new_rows[i - len(self.df["notices"])]
            row.update({k: v for k, v in rec.items() if v != ""}, last_seen=now)
            return False
        df = self.df["notices"]
        for k, v in rec.items():
            if v != "":
                df.iat[i, df.columns.get_loc(k)] = v
        df.iat[i, df.columns.get_loc("last_seen")] = now
        return False

    def log_run(self, source, n_new, n_upd, error=""):
        r = pd.DataFrame([dict(run_at=_now(), source=source, n_new=str(n_new), n_updated=str(n_upd), error=error)])
        self.df["runs"] = pd.concat([self.df["runs"], r], ignore_index=True).tail(500)

    def save_collected(self):
        if self._new_rows:
            self.df["notices"] = pd.concat([self.df["notices"], pd.DataFrame(self._new_rows)], ignore_index=True)
        self._prune()
        self._index()
        self._write("notices", f"공고 수집 {_now()[:16]}")
        self._write("runs", "수집 로그")

    def _prune(self):
        df = self.df["notices"]
        end = pd.to_datetime(df["rcv_end"].str[:10], errors="coerce")
        seen = pd.to_datetime(df["last_seen"], errors="coerce")
        cut = pd.Timestamp(datetime.now() - timedelta(days=KEEP_DAYS))
        old = (end < cut) | (end.isna() & (seen < cut))
        self.df["notices"] = df[~old].reset_index(drop=True)

    def _write(self, name, msg, merge=None):
        for _ in range(3):
            text = self.df[name].to_csv(index=False)
            try:
                self.sha[name] = self.b.write(name, text, self.sha[name], msg)
                return
            except Conflict:
                mine = self.df[name]
                self._load(name)
                self.df[name] = merge(self.df[name], mine) if merge else \
                    pd.concat([self.df[name], mine]).drop_duplicates(FILES[name][0], keep="last") \
                    if name != "runs" else pd.concat([self.df[name], mine]).drop_duplicates()
        raise RuntimeError(f"{name} 저장 충돌이 반복됩니다. 새로고침 후 다시 시도하세요.")

    # 담당자 입력
    def reviews(self):
        return self.df["reviews"]

    def save_reviews(self, changes, user=""):
        """changes: {ancm_id: {review_status, assignee, memo, end_override}}"""
        if not changes:
            return 0
        now = _now()
        rows = [dict(ancm_id=a, updated_by=user, updated_at=now, **{k: str(v or "") for k, v in c.items()})
                for a, c in changes.items()]
        new = pd.DataFrame(rows).reindex(columns=REVIEW_COLS, fill_value="")
        self.df["reviews"] = pd.concat([self.df["reviews"], new]).drop_duplicates("ancm_id", keep="last")

        def merge(remote, _mine):  # 원격 최신본 위에 내가 바꾼 행만 덮어씀
            return pd.concat([remote, new]).drop_duplicates("ancm_id", keep="last")
        self._write("reviews", f"검토 입력 {len(rows)}건 ({user or '익명'})", merge=merge)
        return len(rows)

    def last_runs(self):
        r = self.df["runs"]
        if r.empty:
            return r
        return r.sort_values("run_at").groupby("source").tail(1)
