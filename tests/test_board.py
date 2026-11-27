import io
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import app as board
from services.store import Local


class BoardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Local(tmp.name)
        store_patch = patch.object(board, "store", self.store)
        store_patch.start()
        self.addCleanup(store_patch.stop)
        self.client = board.app.test_client()
        self.assertEqual(self.client.get("/").status_code, 200)
        with self.client.session_transaction() as session:
            self.token = session["csrf"]

    def submit(self, path, **data):
        return self.client.post(path, data=dict(csrf=self.token, **data))

    def test_discussion(self):
        with patch.object(board, "rate_limit"):
            photo = io.BytesIO()
            Image.new("RGB", (12, 12)).save(photo, "PNG")
            photo.seek(0)
            response = self.submit("/post", message="数学の復習", title="<math>", category="勉強",
                                   image=(photo, "../../name.png"))
            self.assertEqual(response.status_code, 303)
            path = response.location
            self.assertIn("&lt;math&gt;", self.client.get(path).text)
            self.assertEqual(self.client.get(path.replace("/p/", "/image/")).mimetype, "image/jpeg")
            for query, visible in [("q=数学", True), ("category=進路", False), ("unanswered=on", True)]:
                self.assertEqual("&lt;math&gt;" in self.client.get("/?" + query).text, visible)
            self.assertEqual(self.submit(path + "/comment", message="教科書から").status_code, 303)
            self.assertNotIn("&lt;math&gt;", self.client.get("/?unanswered=on").text)
            self.assertIn("教科書から", self.client.get(path).text)
            for action in ("like", "like", "report"):
                self.assertEqual(self.submit(path + "/" + action).status_code, 303)
            self.assertEqual(len(self.store.rows("like")), 1)
            other = board.app.test_client()
            other.get("/")
            self.assertIn("&lt;math&gt;", self.client.get("/?view=mine").text)
            self.assertNotIn("&lt;math&gt;", other.get("/?view=mine").text)
            with other.session_transaction() as session:
                token = session["csrf"]
            self.assertEqual(other.post(path + "/resolved", data={"csrf": token}).status_code, 403)
            self.assertEqual(self.submit(path + "/resolved").status_code, 303)
            self.assertEqual(self.submit(path + "/comment", message="回答").status_code, 409)
            self.assertEqual(other.post(path + "/deleted", data={"csrf": token}).status_code, 403)
            self.assertEqual(self.submit(path + "/deleted").status_code, 303)
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.get(path.replace("/p/", "/image/")).status_code, 404)
            self.assertEqual(Local(self.store.root).rows("board")[0]["text"], "数学の復習")

    def test_validation(self):
        self.assertEqual(self.client.post("/post").status_code, 403)
        self.assertEqual(self.submit("/post", message=" ").status_code, 400)
        self.assertEqual(self.submit("/post", message="質問", image=(io.BytesIO(b"bad"), "x.jpg")).status_code, 400)
        self.assertEqual(self.submit("/post", message="質問", category="bad").status_code, 400)
        with patch("app.time") as clock:
            clock.time.return_value = 10000
            self.assertEqual(self.submit("/post", message="質問").status_code, 303)
            self.assertEqual(self.submit("/post", message="質問").status_code, 429)
        with self.client.get("/static/index.html") as response:
            self.assertEqual(response.status_code, 200)
