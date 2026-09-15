import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from store import Store, LocalFiles, Conflict


def _it(i, **kw):
    d = dict(ancm_id=f"IRIS:{i}", source="IRIS", title=f"공고{i}", rcv_end="2099-01-01")
    d.update(kw)
    return d


def test_upsert_and_reviews_persist():
    root = tempfile.mkdtemp()
    s = Store(LocalFiles(root))
    assert s.upsert(_it(1)) and not s.upsert(_it(1, contact="x"))
    s.save_collected()
    s.save_reviews({"IRIS:1": dict(review_status="검토중", assignee="홍길동", memo="", end_override="")}, "tester")
    s2 = Store(LocalFiles(root))
    assert s2.known("IRIS:1")["contact"] == "x"
    s2.upsert(_it(1, title="수정된 제목", contact=""))
    s2.save_collected()
    s3 = Store(LocalFiles(root))
    assert s3.known("IRIS:1")["title"] == "수정된 제목" and s3.known("IRIS:1")["contact"] == "x"
    assert s3.reviews().set_index("ancm_id").loc["IRIS:1", "assignee"] == "홍길동"


def test_prune_old():
    root = tempfile.mkdtemp()
    s = Store(LocalFiles(root))
    s.upsert(_it(1, rcv_end="2020-01-01")); s.upsert(_it(2))
    s.save_collected()
    assert Store(LocalFiles(root)).known("IRIS:1") is None


class FlakyBackend(LocalFiles):
    """첫 저장에서 다른 사람이 먼저 커밋한 상황을 흉내냄."""
    def __init__(self, root):
        super().__init__(root); self.fail = True

    def write(self, name, text, sha, message):
        if name == "reviews" and self.fail:
            self.fail = False
            other = "ancm_id,review_status,assignee,memo,end_override,updated_by,updated_at\nIRIS:9,제외,,,,,\n"
            super().write(name, other, None, "")
            raise Conflict("sha mismatch")
        return super().write(name, text, sha, message)


def test_review_conflict_merges():
    root = tempfile.mkdtemp()
    s = Store(FlakyBackend(root))
    s.save_reviews({"IRIS:1": dict(review_status="검토중", assignee="", memo="", end_override="")})
    ids = set(Store(LocalFiles(root)).reviews()["ancm_id"])
    assert ids == {"IRIS:1", "IRIS:9"}
