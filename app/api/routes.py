from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from datetime import datetime
from app.extensions.db import get_db
from app.models.models import ALLOWED_COLLECTIONS, to_json, CONTACT_MESSAGES
from app.utils.helpers import send_email

api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health_check():
    """Lightweight health endpoint — does not touch the database.

    Use this to verify the serverless function is running even when the DB
    is unreachable.
    """
    return jsonify({"status": "ok"}), 200

def get_collection(name):
    if name not in ALLOWED_COLLECTIONS:
        return None
    try:
        return get_db().get_collection(name)
    except Exception:
        # Fail-safe: if the database client cannot be created/used (network
        # issue, misconfiguration, etc.) treat as missing collection so the
        # route handlers can return a 4xx/5xx without crashing the function.
        return None


@api.route("/<string:collection>", methods=["GET", "POST"])
def list_create(collection):
    coll = get_collection(collection)
    # PyMongo Collection objects do not support truth-value testing.
    # Explicitly compare with None per pymongo's guidance.
    if coll is None:
        return jsonify({"error": "Invalid collection"}), 404

    if request.method == "GET":
        data = list(coll.find())
        return jsonify([to_json(d) for d in data])

    payload = request.json
    # Special handling for contact_messages: validate fields, attach timestamps
    if collection == CONTACT_MESSAGES:
        if not payload or not isinstance(payload, dict):
            return jsonify({"error": "Invalid payload"}), 400

        full_name = payload.get("full_name")
        email = payload.get("email")
        message = payload.get("message")
        # basic validation
        if not full_name or not email or not message:
            return jsonify({"error": "full_name, email and message are required"}), 400

        # if product_id included, try to convert to ObjectId
        pid = payload.get("product_id")
        if pid:
            try:
                payload["product_id"] = ObjectId(pid)
            except Exception:
                # keep as-is (maybe not an ObjectId)
                payload["product_id"] = pid

        payload["created_at"] = datetime.utcnow()
        payload["updated_at"] = datetime.utcnow()

        result = coll.insert_one(payload)

        # Optionally send confirmation email to user. Controlled by query param
        # ?send_email=true (default if SMTP configured). To explicitly disable set send_email=false
        send_email_param = request.args.get("send_email")
        should_send = True if send_email_param is None else send_email_param.lower() not in ("0", "false")
        email_sent = False
        if should_send:
            try:
                print(f"Attempting to send confirmation email to {email} for contact message from {full_name}")
                subject = "We've received your message"
                body = f"""
                    Hi {full_name},

                    Thanks for reaching out! 😊

                    We've received your message and will review it shortly. Our team will respond as soon as possible.

                    Here’s a copy of your message:
                    --------------------------------
                    {message}

                    We appreciate your patience.

                    Warm regards,
                    Customer Support Team
                    """

                admin_body = f"""
                    Hello Admin,

                    You have received a new inquiry from your website.

                    User Details:
                    -------------
                    Name   : {full_name}
                    Email  : {email}
                    Subject: {subject}

                    Message:
                    {message}

                    Please respond to the user as soon as possible.

                    Regards,
                    Your Website System
                    """

                if payload.get("product_id"):
                    body += f"\nRelated product: {payload.get('product_id')}\n"
                email_sent = send_email(email, subject, body,admin_body)
            except Exception:
                email_sent = False

        return jsonify({"id": str(result.inserted_id), "email_sent": bool(email_sent)}), 201

    # Generic insert for other collections
    result = coll.insert_one(payload)
    return jsonify({"id": str(result.inserted_id)}), 201


@api.route("/<string:collection>/<string:id>", methods=["GET", "PUT", "DELETE"])
def detail(collection, id):
    coll = get_collection(collection)
    # PyMongo Collection objects do not support truth-value testing.
    # Explicitly compare with None per pymongo's guidance.
    if coll is None:
        return jsonify({"error": "Invalid collection"}), 404

    oid = ObjectId(id)

    if request.method == "GET":
        return jsonify(to_json(coll.find_one({"_id": oid})))

    if request.method == "PUT":
        coll.update_one({"_id": oid}, {"$set": request.json})
        return jsonify({"updated": True})

    coll.delete_one({"_id": oid})
    return jsonify({"deleted": True})


@api.route("/collections/popular", methods=["GET"])
def categories_with_popular_products():
    """Return categories and only products marked as popular (is_populer == True).

    Response format:
    {
      "categories": [ ... ],
      "products": [ ... ]  # only documents where is_populer is truthy
    }
    """
    cat_coll = get_collection("categories")
    prod_coll = get_collection("products")

    if cat_coll is None or prod_coll is None:
        return jsonify({"error": "Required collections not available"}), 404

    categories = list(cat_coll.find())
    # note: stored field name is `is_populer` (as used throughout the admin UI)
    products = list(prod_coll.find({"is_populer": True}))

    return jsonify({
        "categories": [to_json(c) for c in categories],
        "products": [to_json(p) for p in products],
    })


@api.route("/categories/popular", methods=["GET"])
def popular_categories():
    """Return only categories marked as popular (is_populer == True)."""
    cat_coll = get_collection("categories")
    if cat_coll is None:
        return jsonify({"error": "Categories collection not available"}), 404
    cats = list(cat_coll.find({"is_populer": True}))
    return jsonify([to_json(c) for c in cats])


@api.route("/products/popular", methods=["GET"])
def popular_products():
    """Return only products marked as popular (is_populer == True)."""
    prod_coll = get_collection("products")
    if prod_coll is None:
        return jsonify({"error": "Products collection not available"}), 404
    prods = list(prod_coll.find({"is_populer": True}))
    return jsonify([to_json(p) for p in prods])
