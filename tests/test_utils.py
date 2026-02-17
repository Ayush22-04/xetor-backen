import os
from flask import Flask

from app.utils.helpers import send_email
from app.utils.helpers import upload_to_imgbb
import base64
import io
from werkzeug.datastructures import FileStorage
try:
    from PIL import Image
except Exception:  # pragma: no cover - Pillow may be absent in some envs
    Image = None


def test_send_email_outside_app_context_returns_false():
    # When called outside a Flask app context and no MAIL_SERVER env var,
    # send_email should return False (no SMTP configured).
    os.environ.pop("MAIL_SERVER", None)
    assert send_email("foo@example.com", "subj", "body") is False


def test_send_email_with_app_context_and_suppressed_send_returns_true():
    app = Flask(__name__)
    # minimal mail config - prevent actual sending
    app.config["MAIL_SERVER"] = "localhost"
    app.config["MAIL_SUPPRESS_SEND"] = True

    with app.app_context():
        # initialize extension if needed and call send_email
        from app.extensions.mail import mail as mail_ext

        mail_ext.init_app(app)
        assert send_email("foo@example.com", "subj", "body") is True


def test_send_email_fallback_to_smtp(monkeypatch):
    app = Flask(__name__)
    app.config["MAIL_SERVER"] = "localhost"
    app.config["MAIL_PORT"] = 25
    app.config["MAIL_SUPPRESS_SEND"] = False

    sent = {}

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            sent['connected'] = (host, port)

        def starttls(self):
            sent['tls'] = True

        def login(self, user, password):
            sent['login'] = (user, bool(password))

        def send_message(self, msg):
            sent['sent_msg'] = True

        def quit(self):
            sent['quit'] = True

    # Make Mail.send raise to force fallback
    with app.app_context():
        from app.extensions.mail import mail as mail_ext
        def raise_send(msg):
            raise Exception("boom")

        monkeypatch.setattr(mail_ext, 'send', raise_send)
        monkeypatch.setattr('smtplib.SMTP', DummySMTP)
        assert send_email("foo@example.com", "subj", "body") is True
        assert sent.get('sent_msg') is True


def test_upload_to_imgbb_compresses_image(monkeypatch):
    # create a large in-memory JPEG to force compression
    if Image is None:
        return

    buf = io.BytesIO()
    img = Image.new("RGB", (3000, 2000), color="white")
    img.save(buf, format="JPEG", quality=95)
    orig = buf.getvalue()
    buf.seek(0)

    fs = FileStorage(stream=io.BytesIO(orig), filename="large.jpg", content_type="image/jpeg")

    original_b64_len = len(base64.b64encode(orig).decode("utf-8"))

    captured = {}

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"display_url": "https://imgbb.test/1.jpg"}}

    def fake_post(url, data=None, timeout=None):
        captured['b64_len'] = len(data.get('image', ''))
        return DummyResp()

    monkeypatch.setattr('requests.post', fake_post)

    res = upload_to_imgbb(fs)
    assert res == "https://imgbb.test/1.jpg"
    # ensure the uploaded base64 payload is smaller than the original
    assert captured.get('b64_len', 0) < original_b64_len


def test_upload_to_imgbb_non_image_passes_through(monkeypatch):
    raw = b"this is not an image"
    fs = FileStorage(stream=io.BytesIO(raw), filename="file.bin", content_type="application/octet-stream")

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"display_url": "https://imgbb.test/file.bin"}}

    def fake_post(url, data=None, timeout=None):
        uploaded_b64 = data.get('image')
        decoded = base64.b64decode(uploaded_b64)
        assert decoded == raw
        return DummyResp()

    monkeypatch.setattr('requests.post', fake_post)
    res = upload_to_imgbb(fs)
    assert res == "https://imgbb.test/file.bin"
