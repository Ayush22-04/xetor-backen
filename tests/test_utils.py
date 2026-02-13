import os
from flask import Flask

from app.utils.helpers import send_email


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
