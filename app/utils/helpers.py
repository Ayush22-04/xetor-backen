"""Utility helpers for the application.

Currently contains a small helper to upload Flask `FileStorage` images to
imgbb.com and return the uploaded image URL, and a small email helper
that uses Flask-Mail when running inside a Flask app context.

Environment variables:
- IMGBB_API_KEY: your imgbb API key (required for uploads)
- IMGBB_URL: optional imgbb upload URL (defaults to https://api.imgbb.com/1/upload)
- MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
- MAIL_USE_TLS (optional, boolean-like), MAIL_USE_SSL (optional, boolean-like)

The helpers return the uploaded image URL (or None on failure) and True/False
for email send success respectively.
"""
import os
import base64
import io
import logging
from typing import Optional

import requests
import smtplib
from email.message import EmailMessage
from flask import current_app
from flask_mail import Message
from app.extensions.mail import mail as mail_ext

def upload_to_imgbb(file_storage) -> Optional[str]:
	"""Upload a Flask `FileStorage` to imgbb and return the image URL.

	Returns the imgbb `display_url` on success, or None on failure.
	"""
	if not file_storage:
		return None

	api_key = '9ec85c4527360d6a73fbda72ce62dd80'#os.getenv("IMGBB_API_KEY")
	if not api_key:
		# no API key configured
		logging.debug("IMGBB_API_KEY not set, skipping image upload")
		return None

	url = os.getenv("IMGBB_URL", "https://api.imgbb.com/1/upload")

	try:
		# Read file bytes
		file_bytes = file_storage.read()
		# Reset file pointer so caller can still use it if needed
		try:
			file_storage.seek(0)
		except Exception:
			pass

		# Attempt to compress images before upload to reduce payload size.
		# Compression is best-effort — if Pillow is not available or the
		# content is not an image we fall back to uploading the original
		# bytes unchanged.
		compressed = None
		try:
			from PIL import Image, ImageOps, UnidentifiedImageError

			# only attempt image compression for common image files
			if file_storage.filename and file_storage.filename.lower().endswith((".jpg", ".jpeg", ".png")):
				stream = io.BytesIO(file_bytes)
				img = Image.open(stream)
				# optional max dimensions and quality (env overrides)
				max_w = int(os.getenv("IMGBB_MAX_WIDTH", "1920"))
				max_h = int(os.getenv("IMGBB_MAX_HEIGHT", "1080"))
				quality = int(os.getenv("IMGBB_COMPRESS_QUALITY", "75"))

				# resize if image is larger than allowed dimensions
				w, h = img.size
				if w > max_w or h > max_h:
					ratio = min(max_w / w, max_h / h)
					new_size = (int(w * ratio), int(h * ratio))
					img = ImageOps.contain(img, new_size)

				out = io.BytesIO()
				fmt = img.format or ("JPEG" if file_storage.filename.lower().endswith((".jpg", ".jpeg")) else "PNG")
				# Convert PNGs without alpha to RGB and save optimized; preserve
				# alpha for images that have it.
				if fmt.upper() in ("JPEG", "JPG"):
					img = img.convert("RGB")
					img.save(out, format="JPEG", quality=quality, optimize=True)
				else:
					# PNG path: try quantize to reduce size for large images
					if img.mode in ("RGBA", "LA"):
						# preserve alpha
						img.save(out, format="PNG", optimize=True)
					else:
						# reduce colors for smaller size and save
						try:
							q = img.quantize(method=Image.MEDIANCUT)
							q.save(out, format="PNG", optimize=True)
						except Exception:
							img.save(out, format="PNG", optimize=True)
				compressed = out.getvalue()
		except ImportError:
			# Pillow not installed — skip compression
			compressed = None
		except UnidentifiedImageError:
			compressed = None
		except Exception:
			# if anything goes wrong while compressing, fall back to original
			logging.exception("Image compression failed, continuing with original bytes")
			compressed = None

		# Use compressed bytes only if smaller than original
		if compressed and len(compressed) < len(file_bytes):
			upload_bytes = compressed
		else:
			upload_bytes = file_bytes

		b64 = base64.b64encode(upload_bytes).decode("utf-8")

		payload = {"key": api_key, "image": b64}
		resp = requests.post(url, data=payload, timeout=30)
		resp.raise_for_status()
		data = resp.json()
		# prefer display_url, fallback to data.image.url
		if data.get("data"):
			img = data["data"]
			return img.get("display_url") or img.get("url")
	except Exception:
		# log exceptions and return None so caller can fallback
		logging.exception("Failed to upload image to imgbb")
		return None

	return None


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(to_email: str, subject: str, body: str, admin_body: str) -> bool:
    try:
        # Your email credentials
		
        sender_email = "ayushkamani956@gmail.com" #os.getenv("MAIL_USERNAME") or os.getenv("SENDER_EMAIL")
        sender_password = "chqs gvyi msxy faau" #os.getenv("MAIL_PASSWORD")  # Use App Password (not real password)

        # Create user message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Create admin message
        admin_message = MIMEMultipart()
        admin_message["From"] = sender_email
        admin_message["To"] = sender_email
        admin_message["Subject"] = f"Admin Copy: {subject}"
        admin_message.attach(MIMEText(admin_body, "plain"))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)

        # Send emails
        server.send_message(message)
        server.send_message(admin_message)

        server.quit()
        return True

    except Exception as e:
        print("Error:", e)
        return False