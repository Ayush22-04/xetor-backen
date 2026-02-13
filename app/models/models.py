from bson.objectid import ObjectId
from datetime import datetime
from decimal import Decimal

ADMIN_USERS = "admin_users"
HOME_HEROES = "home_heroes"
CATEGORIES = "categories"
PRODUCTS = "products"
CONTACT_MESSAGES = "contact_messages"
TESTIMONIALS = "testimonials"

# Show only collections that should be editable/viewable from the
# admin "collections" UI. Keep admin users and other internal
# collections out of this list so the admin collections list shows
# only the collections the user requested.
ALLOWED_COLLECTIONS = {
    CATEGORIES,
    PRODUCTS,
    CONTACT_MESSAGES,
    TESTIMONIALS,
}

def to_json(doc):
    """Recursively convert a MongoDB document (or value) into JSON-serializable types.

    - ObjectId -> str
    - datetime -> ISO 8601 string
    - Decimal -> str (preserve precision)
    - bson.decimal128.Decimal128 -> str
    Works for nested dicts and lists.
    """
    if doc is None:
        return None

    try:
        # Decimal128 is optional depending on bson version
        from bson.decimal128 import Decimal128
    except Exception:
        Decimal128 = None

    def convert(obj):
        # dict-like
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        # lists/tuples
        if isinstance(obj, (list, tuple)):
            return [convert(v) for v in obj]
        # ObjectId -> string
        if isinstance(obj, ObjectId):
            return str(obj)
        # datetime -> ISO
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Decimal -> string
        if isinstance(obj, Decimal):
            return str(obj)
        # bson Decimal128 -> string (to_decimal may raise, fallback to str)
        if Decimal128 is not None and isinstance(obj, Decimal128):
            try:
                return str(obj.to_decimal())
            except Exception:
                return str(obj)
        return obj

    return convert(doc)
