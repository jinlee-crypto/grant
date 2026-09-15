"""GitHub Contents API 호출 형식 확인 (네트워크 없이 가짜 응답)."""
import base64, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import store


class Resp:
    def __init__(self, code, js=None, content=b""):
        self.status_code, self._js, self.content, self.text = code, js, content, str(js)
    def json(self): return self._js
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


def test_github_roundtrip(monkeypatch):
    files = {}
    def get(url, headers=None, params=None, timeout=None):
        name = url.rsplit("/", 1)[-1]
        if name not in files: return Resp(404)
        if headers["Accept"].endswith("raw"): return Resp(200, content=files[name][0])
        return Resp(200, {"sha": files[name][1]})
    def put(url, headers=None, json=None, timeout=None):
        name = url.rsplit("/", 1)[-1]
        if name in files and json.get("sha") != files[name][1]:
            return Resp(409, {"message": "sha does not match"})
        sha = f"s{len(files)}{name}"
        files[name] = (base64.b64decode(json["content"]), sha)
        assert json["branch"] == "data"
        return Resp(200, {"content": {"sha": sha}})
    monkeypatch.setattr(store.requests, "get", get)
    monkeypatch.setattr(store.requests, "put", put)
    b = store.backend_from_env({"GITHUB_REPO": "me/grants", "GITHUB_TOKEN": "t"})
    assert isinstance(b, store.GitHubFiles)
    s = store.Store(b)
    s.upsert(dict(ancm_id="IRIS:1", source="IRIS", title="한글 제목", rcv_end="2099-01-01"))
    s.save_collected()
    s.save_reviews({"IRIS:1": dict(review_status="검토중", assignee="김", memo="", end_override="")})
    s2 = store.Store(b)
    assert s2.known("IRIS:1")["title"] == "한글 제목"
    assert s2.reviews().iloc[0]["assignee"] == "김"
    s2.save_reviews({"IRIS:1": dict(review_status="제외", assignee="", memo="", end_override="")})  # 두 번째 커밋(sha 갱신)
