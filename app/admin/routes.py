from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from app.extensions.db import get_db
from app.models.models import ADMIN_USERS, to_json, ALLOWED_COLLECTIONS, HOME_HEROES, CATEGORIES, PRODUCTS, CONTACT_MESSAGES, TESTIMONIALS
from app.admin.auth import login_required, current_admin
from bson.objectid import ObjectId
import bcrypt
import os
from flask import current_app
from werkzeug.utils import secure_filename
from app.utils.helpers import upload_to_imgbb
from datetime import datetime


admin_bp = Blueprint("admin", __name__, template_folder="../templates")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password", "").encode("utf-8")

        db = get_db()
        user = db[ADMIN_USERS].find_one({"username": username})
        if user and user.get("password"):
            stored = user["password"].encode("utf-8")
            if bcrypt.checkpw(password, stored):
                session["admin_user_id"] = str(user["_id"])
                session["admin_username"] = user.get("username")
                flash("Logged in successfully.", "success")
                # dashboard route was replaced by collections_list at '/'
                return redirect(url_for("admin.collections_list"))

        flash("Invalid username or password.", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    flash("Logged out.", "info")
    return redirect(url_for("admin.login"))


# @admin_bp.route("/")
# @login_required
# def dashboard():
#     db = get_db()
#     users_count = db[ADMIN_USERS].count_documents({})
#     return render_template("admin/dashboard.html", users_count=users_count, admin=current_admin())


@admin_bp.route("/users")
@login_required
def users_list():
    db = get_db()
    docs = list(db[ADMIN_USERS].find({}))
    users = [to_json(d) for d in docs]
    return render_template("admin/users_list.html", users=users, admin=current_admin())


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
def users_create():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password", "").encode("utf-8")
        if not username or not password:
            flash("Username and password are required.", "warning")
            return render_template("admin/user_form.html", admin=current_admin())

        hashed = bcrypt.hashpw(password, bcrypt.gensalt())
        db = get_db()
        db[ADMIN_USERS].insert_one({"username": username, "password": hashed.decode("utf-8")})
        flash("Admin user created.", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", admin=current_admin())


@admin_bp.route("/users/<id>/edit", methods=["GET", "POST"])
@login_required
def users_edit(id):
    db = get_db()
    obj = db[ADMIN_USERS].find_one({"_id": ObjectId(id)})
    if not obj:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users_list"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password", None)
        update = {"username": username}
        if password:
            update["password"] = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db[ADMIN_USERS].update_one({"_id": obj["_id"]}, {"$set": update})
        flash("User updated.", "success")
        return redirect(url_for("admin.users_list"))

    user = to_json(obj)
    return render_template("admin/user_form.html", user=user, admin=current_admin())


@admin_bp.route("/users/<id>/delete", methods=["GET", "POST"])
@login_required
def users_delete(id):
    db = get_db()
    obj = db[ADMIN_USERS].find_one({"_id": ObjectId(id)})
    if not obj:
        flash("User not found.", "warning")
        return redirect(url_for("admin.users_list"))

    if request.method == "POST":
        db[ADMIN_USERS].delete_one({"_id": obj["_id"]})
        flash("User deleted.", "info")
        return redirect(url_for("admin.users_list"))

    user = to_json(obj)
    return render_template("admin/confirm_delete.html", user=user, admin=current_admin())


@admin_bp.route("/")
@login_required
def collections_list():
    """Show all allowed collections and their document counts."""
    db = get_db()
    items = []
    for coll in sorted(ALLOWED_COLLECTIONS):
        try:
            count = db[coll].count_documents({})
        except Exception:
            count = 0
        items.append({"name": coll, "count": count})
    return render_template("admin/collections_list.html", collections=items, admin=current_admin())


@admin_bp.route("/collections/<coll>/docs")
@login_required
def docs_list(coll):
    if coll not in ALLOWED_COLLECTIONS:
        flash("Collection not allowed.", "warning")
        return redirect(url_for("admin.collections_list"))
    db = get_db()
    docs = list(db[coll].find({}).limit(200))
    docs = [to_json(d) for d in docs]

    # For home_heroes, format datetimes to ISO strings for display
    if coll == HOME_HEROES:
        for d in docs:
            if d.get("created_at") and isinstance(d.get("created_at"), datetime):
                d["created_at"] = d.get("created_at").isoformat()
            if d.get("updated_at") and isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d.get("updated_at").isoformat()
    # For categories, format datetimes as well
    if coll == CATEGORIES:
        for d in docs:
            if d.get("created_at") and isinstance(d.get("created_at"), datetime):
                d["created_at"] = d.get("created_at").isoformat()
            if d.get("updated_at") and isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d.get("updated_at").isoformat()
    # For products, format datetimes and resolve category names
    if coll == PRODUCTS:
        # collect category ids from raw DB docs
        cat_ids = set()
        for d in docs:
            cid = d.get("category_id")
            if cid:
                cat_ids.add(cid)
        # fetch category names
        cat_map = {}
        if cat_ids:
            # convert to ObjectId if necessary
            q_ids = []
            for x in cat_ids:
                try:
                    q_ids.append(ObjectId(x))
                except Exception:
                    # already an ObjectId?
                    try:
                        q_ids.append(x)
                    except Exception:
                        pass
            cats = list(get_db()[CATEGORIES].find({"_id": {"$in": q_ids}}))
            for c in cats:
                cat_map[str(c["_id"])]=c.get("name")

        for d in docs:
            if d.get("created_at") and isinstance(d.get("created_at"), datetime):
                d["created_at"] = d.get("created_at").isoformat()
            if d.get("updated_at") and isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d.get("updated_at").isoformat()
            # normalize category_id to string and attach category_name
            cid = d.get("category_id")
            if cid:
                try:
                    cid_str = str(cid)
                except Exception:
                    cid_str = cid
                d["category_id"] = cid_str
                d["category_name"] = cat_map.get(cid_str, "-")
    # For contact_messages, format datetimes for display
    if coll == CONTACT_MESSAGES:
        for d in docs:
            if d.get("created_at") and isinstance(d.get("created_at"), datetime):
                d["created_at"] = d.get("created_at").isoformat()
            if d.get("updated_at") and isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d.get("updated_at").isoformat()
        # resolve product names for any referenced product_id
        prod_ids = set()
        for d in docs:
            pid = d.get("product_id")
            if pid:
                try:
                    prod_ids.add(str(pid))
                except Exception:
                    prod_ids.add(pid)
        if prod_ids:
            q_ids = []
            for x in prod_ids:
                try:
                    q_ids.append(ObjectId(x))
                except Exception:
                    q_ids.append(x)
            products = list(get_db()[PRODUCTS].find({"_id": {"$in": q_ids}}))
            prod_map = {str(p["_id"]): p.get("name") for p in products}
            for d in docs:
                pid = d.get("product_id")
                if pid:
                    try:
                        pid_str = str(pid)
                    except Exception:
                        pid_str = pid
                    d["product_id"] = pid_str
                    d["product_name"] = prod_map.get(pid_str, "-")

    # For testimonials, format datetimes and normalize rating for display
    if coll == TESTIMONIALS:
        for d in docs:
            if d.get("created_at") and isinstance(d.get("created_at"), datetime):
                d["created_at"] = d.get("created_at").isoformat()
            if d.get("updated_at") and isinstance(d.get("updated_at"), datetime):
                d["updated_at"] = d.get("updated_at").isoformat()
            if d.get("rating") is not None:
                try:
                    d["rating"] = int(d.get("rating"))
                except Exception:
                    pass

    return render_template("admin/docs_list.html", coll=coll, docs=docs, admin=current_admin())


@admin_bp.route("/collections/<coll>/docs/create", methods=["GET", "POST"])
@login_required
def docs_create(coll):
    if coll not in ALLOWED_COLLECTIONS:
        flash("Collection not allowed.", "warning")
        return redirect(url_for("admin.collections_list"))
    # Special handling for home_heroes: provide a form with file upload and boolean
    if coll == HOME_HEROES:
        if request.method == "POST":
            title = request.form.get("title")
            is_active = bool(request.form.get("is_active"))

            hero_file = request.files.get("hero_image")
            hero_url = None
            if hero_file and hero_file.filename:
                # Upload only to imgbb; do NOT store files locally.
                hero_url = upload_to_imgbb(hero_file)
                if not hero_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    return render_template("admin/home_hero_form.html", coll=coll, data=request.form, admin=current_admin())
            doc = {
                "title": title,
                "is_active": is_active,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if hero_url:
                doc["hero_image"] = hero_url

            db = get_db()
            db[coll].insert_one(doc)
            flash("Document created.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        return render_template("admin/home_hero_form.html", coll=coll, data={}, admin=current_admin())
    
    # Special handling for categories (name, description, image, is_active, timestamps)
    if coll == CATEGORIES:
        if request.method == "POST":
            name = request.form.get("name")
            description = request.form.get("description")
            is_active = bool(request.form.get("is_active"))
            # new field: is_populer (boolean)
            is_populer = bool(request.form.get("is_populer"))
            # new field: is_populer (boolean)
            is_populer = bool(request.form.get("is_populer"))

            img_file = request.files.get("image")
            img_url = None
            if img_file and img_file.filename:
                # Upload only to imgbb; do NOT store files locally.
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    return render_template("admin/category_form.html", coll=coll, data=request.form, admin=current_admin())

            doc = {
                "name": name,
                "description": description,
                "is_active": is_active,
                "is_populer": is_populer,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if img_url:
                doc["image"] = img_url

            db = get_db()
            db[coll].insert_one(doc)
            flash("Category created.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        return render_template("admin/category_form.html", coll=coll, data={}, admin=current_admin())

    # Generic JSON editor for other collections
    # Special handling for contact messages: provide a simple create form
    if coll == CONTACT_MESSAGES:
        # provide optional product choices to associate a message with a product
        products = list(get_db()[PRODUCTS].find({}))
        products = [to_json(p) for p in products]

        if request.method == "POST":
            full_name = request.form.get("full_name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            message = request.form.get("message")
            product_id = request.form.get("product_id")

            if not full_name or not email or not message:
                flash("Full name, email and message are required.", "warning")
                return render_template("admin/contact_message_form.html", coll=coll, data=request.form, products=products, admin=current_admin())

            doc = {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "message": message,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if product_id:
                try:
                    doc["product_id"] = ObjectId(product_id)
                except Exception:
                    doc["product_id"] = product_id
            db = get_db()
            db[coll].insert_one(doc)
            flash("Contact message created.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        return render_template("admin/contact_message_form.html", coll=coll, data={}, products=products, admin=current_admin())


    # email_test route was accidentally defined inside `docs_create` which causes
    # Flask to attempt to register a new blueprint route at request-time.
    # Keep the route defined at module-level (see below) so the blueprint is
    # fully configured before being registered with the app.

    # Special handling for testimonials (name, role, content, rating, email, optional image, is_active)
    if coll == TESTIMONIALS:
        if request.method == "POST":
            name = request.form.get("name")
            role = request.form.get("role")
            content = request.form.get("content")
            rating = request.form.get("rating")
            email = request.form.get("email")
            is_active = bool(request.form.get("is_active"))

            # basic validation
            if not name or not content:
                flash("Name and content are required.", "warning")
                return render_template("admin/testimonial_form.html", coll=coll, data=request.form, admin=current_admin())

            # normalize rating to int if possible
            try:
                rating_val = int(rating) if rating else None
                if rating_val is not None and (rating_val < 1 or rating_val > 5):
                    raise ValueError("Rating must be between 1 and 5")
            except Exception:
                flash("Rating must be an integer between 1 and 5.", "warning")
                return render_template("admin/testimonial_form.html", coll=coll, data=request.form, admin=current_admin())

            img_file = request.files.get("image")
            img_url = None
            if img_file and img_file.filename:
                # Upload only to imgbb; do NOT store files locally.
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    return render_template("admin/testimonial_form.html", coll=coll, data=request.form, admin=current_admin())

            doc = {
                "name": name,
                "role": role,
                "content": content,
                "rating": rating_val,
                "email": email,
                "is_active": is_active,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if img_url:
                doc["image"] = img_url

            db = get_db()
            db[coll].insert_one(doc)
            flash("Testimonial created.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        return render_template("admin/testimonial_form.html", coll=coll, data={}, admin=current_admin())
    if coll == PRODUCTS:
        # provide category choices for product creation
        cats = list(get_db()[CATEGORIES].find({}))
        cats = [to_json(c) for c in cats]
        if request.method == "POST":
            name = request.form.get("name")
            description = request.form.get("description")
            price = request.form.get("price")
            is_active = bool(request.form.get("is_active"))
            # new field: is_populer (boolean)
            is_populer = bool(request.form.get("is_populer"))
            img_file = request.files.get("image")
            category_id = request.form.get("category_id")
            try:
                price_val = int(price) if price else 0
            except Exception:
                flash("Price must be an integer.", "warning")
                return render_template("admin/product_form.html", coll=coll, cats=cats, data=request.form, admin=current_admin())

            doc = {
                "name": name,
                "description": description,
                "price": price_val,
                "is_active": is_active,
                "is_populer": is_populer,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            if category_id:
                try:
                    doc["category_id"] = ObjectId(category_id)
                except Exception:
                    doc["category_id"] = category_id
            # handle image upload (imgbb only; do NOT store locally)
            img_url = None
            if img_file and img_file.filename:
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    return render_template("admin/product_form.html", coll=coll, cats=cats, data=request.form, admin=current_admin())
            if img_url:
                doc["image"] = img_url

            db = get_db()
            db[coll].insert_one(doc)
            flash("Product created.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        return render_template("admin/product_form.html", coll=coll, cats=cats, data={}, admin=current_admin())


    @admin_bp.route("/email/test", methods=["GET", "POST"])
    @login_required
    def email_test():
        """Send a test email (kept at module level so blueprint routes are
        registered during app setup)."""
        result = None
        if request.method == "POST":
            to_email = request.form.get("to_email")
            subject = request.form.get("subject") or "Test message from Xetor"
            body = request.form.get("body") or "This is a test message."
            # Note: actual send logic kept commented in original code.

        return render_template("admin/test_email.html", admin=current_admin(), result=result)
    if request.method == "POST":
        data = request.form.get("data")
        try:
            import json

            doc = json.loads(data)
        except Exception as e:
            flash(f"Invalid JSON: {e}", "danger")
            return render_template("admin/doc_form.html", coll=coll, data=data, admin=current_admin())
        db = get_db()
        db[coll].insert_one(doc)
        flash("Document created.", "success")
        return redirect(url_for("admin.docs_list", coll=coll))

    return render_template("admin/doc_form.html", coll=coll, data="{}", admin=current_admin())


@admin_bp.route("/collections/<coll>/docs/<id>/edit", methods=["GET", "POST"])
@login_required
def docs_edit(coll, id):
    if coll not in ALLOWED_COLLECTIONS:
        flash("Collection not allowed.", "warning")
        return redirect(url_for("admin.collections_list"))
    db = get_db()
    obj = db[coll].find_one({"_id": ObjectId(id)})
    if not obj:
        flash("Document not found.", "warning")
        return redirect(url_for("admin.docs_list", coll=coll))
    # Special handling for home_heroes
    if coll == HOME_HEROES:
        if request.method == "POST":
            title = request.form.get("title")
            is_active = bool(request.form.get("is_active"))

            hero_file = request.files.get("hero_image")
            hero_url = None
            if hero_file and hero_file.filename:
                hero_url = upload_to_imgbb(hero_file)
                if not hero_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    doc_json = to_json(obj)
                    if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
                        doc_json["created_at"] = obj.get("created_at").isoformat()
                    if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
                        doc_json["updated_at"] = obj.get("updated_at").isoformat()
                    return render_template("admin/home_hero_form.html", coll=coll, doc=doc_json, admin=current_admin())

            update = {
                "title": title,
                "is_active": is_active,
                "updated_at": datetime.utcnow(),
            }
            if hero_url:
                update["hero_image"] = hero_url

            db[coll].update_one({"_id": obj["_id"]}, {"$set": update})
            flash("Document updated.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        doc_json = to_json(obj)
        # format datetimes for display if present
        if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
            doc_json["created_at"] = obj.get("created_at").isoformat()
        if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
            doc_json["updated_at"] = obj.get("updated_at").isoformat()
        return render_template("admin/home_hero_form.html", coll=coll, doc=doc_json, admin=current_admin())

    # Special handling for contact messages (edit)
    if coll == CONTACT_MESSAGES:
        products = list(get_db()[PRODUCTS].find({}))
        products = [to_json(p) for p in products]
        if request.method == "POST":
            full_name = request.form.get("full_name")
            email = request.form.get("email")
            phone = request.form.get("phone")
            message = request.form.get("message")
            product_id = request.form.get("product_id")

            if not full_name or not email or not message:
                flash("Full name, email and message are required.", "warning")
                return render_template("admin/contact_message_form.html", coll=coll, data=request.form, doc=to_json(obj), products=products, admin=current_admin())

            update = {
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "message": message,
                "updated_at": datetime.utcnow(),
            }
            if product_id:
                try:
                    update["product_id"] = ObjectId(product_id)
                except Exception:
                    update["product_id"] = product_id

            db[coll].update_one({"_id": obj["_id"]}, {"$set": update})
            flash("Contact message updated.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        doc_json = to_json(obj)
        if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
            doc_json["created_at"] = obj.get("created_at").isoformat()
        if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
            doc_json["updated_at"] = obj.get("updated_at").isoformat()
        return render_template("admin/contact_message_form.html", coll=coll, doc=doc_json, products=products, admin=current_admin())

    # Special handling for categories (edit)
    if coll == CATEGORIES:
        if request.method == "POST":
            name = request.form.get("name")
            description = request.form.get("description")
            is_active = bool(request.form.get("is_active"))
            # new field: is_populer (boolean)
            is_populer = bool(request.form.get("is_populer"))

            img_file = request.files.get("image")
            img_url = None
            if img_file and img_file.filename:
                # Upload only to imgbb; do NOT store files locally.
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    doc_json = to_json(obj)
                    if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
                        doc_json["created_at"] = obj.get("created_at").isoformat()
                    if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
                        doc_json["updated_at"] = obj.get("updated_at").isoformat()
                    return render_template("admin/category_form.html", coll=coll, doc=doc_json, admin=current_admin())

            update = {
                "name": name,
                "description": description,
                "is_active": is_active,
                "is_populer": is_populer,
                "updated_at": datetime.utcnow(),
            }
            if img_url:
                update["image"] = img_url

            db[coll].update_one({"_id": obj["_id"]}, {"$set": update})
            flash("Category updated.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        doc_json = to_json(obj)
        if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
            doc_json["created_at"] = obj.get("created_at").isoformat()
        if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
            doc_json["updated_at"] = obj.get("updated_at").isoformat()
        return render_template("admin/category_form.html", coll=coll, doc=doc_json, admin=current_admin())

    # Special handling for testimonials (edit)
    if coll == TESTIMONIALS:
        if request.method == "POST":
            name = request.form.get("name")
            role = request.form.get("role")
            content = request.form.get("content")
            rating = request.form.get("rating")
            email = request.form.get("email")
            is_active = bool(request.form.get("is_active"))

            # basic validation
            if not name or not content:
                flash("Name and content are required.", "warning")
                return render_template("admin/testimonial_form.html", coll=coll, data=request.form, doc=to_json(obj), admin=current_admin())

            try:
                rating_val = int(rating) if rating else None
                if rating_val is not None and (rating_val < 1 or rating_val > 5):
                    raise ValueError()
            except Exception:
                flash("Rating must be an integer between 1 and 5.", "warning")
                return render_template("admin/testimonial_form.html", coll=coll, data=request.form, doc=to_json(obj), admin=current_admin())

            img_file = request.files.get("image")
            img_url = None
            if img_file and img_file.filename:
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    doc_json = to_json(obj)
                    if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
                        doc_json["created_at"] = obj.get("created_at").isoformat()
                    if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
                        doc_json["updated_at"] = obj.get("updated_at").isoformat()
                    return render_template("admin/testimonial_form.html", coll=coll, doc=doc_json, admin=current_admin())

            update = {
                "name": name,
                "role": role,
                "content": content,
                "rating": rating_val,
                "email": email,
                "is_active": is_active,
                "updated_at": datetime.utcnow(),
            }
            if img_url:
                update["image"] = img_url

            db[coll].update_one({"_id": obj["_id"]}, {"$set": update})
            flash("Testimonial updated.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        doc_json = to_json(obj)
        if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
            doc_json["created_at"] = obj.get("created_at").isoformat()
        if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
            doc_json["updated_at"] = obj.get("updated_at").isoformat()
        return render_template("admin/testimonial_form.html", coll=coll, doc=doc_json, admin=current_admin())

    # Generic JSON editor for other collections
    if coll == PRODUCTS:
        # provide category choices for product edit
        cats = list(get_db()[CATEGORIES].find({}))
        cats = [to_json(c) for c in cats]
        if request.method == "POST":
            name = request.form.get("name")
            description = request.form.get("description")
            price = request.form.get("price")
            is_active = bool(request.form.get("is_active"))
            # new field: is_populer (boolean)
            is_populer = bool(request.form.get("is_populer"))
            category_id = request.form.get("category_id")
            img_file = request.files.get("image")
            try:
                price_val = int(price) if price else 0
            except Exception:
                flash("Price must be an integer.", "warning")
                return render_template("admin/product_form.html", coll=coll, cats=cats, data=request.form, doc=to_json(obj), admin=current_admin())

            update = {
                "name": name,
                "description": description,
                "price": price_val,
                "is_active": is_active,
                "is_populer": is_populer,
                "updated_at": datetime.utcnow(),
            }
            if category_id:
                try:
                    update["category_id"] = ObjectId(category_id)
                except Exception:
                    update["category_id"] = category_id
            # handle image upload (imgbb only; do NOT store locally)
            img_url = None
            if img_file and img_file.filename:
                img_url = upload_to_imgbb(img_file)
                if not img_url:
                    flash("Image upload failed. Please check IMGBB_API_KEY and try again.", "danger")
                    return render_template("admin/product_form.html", coll=coll, cats=cats, data=request.form, doc=to_json(obj), admin=current_admin())
            if img_url:
                update["image"] = img_url

            db[coll].update_one({"_id": obj["_id"]}, {"$set": update})
            flash("Product updated.", "success")
            return redirect(url_for("admin.docs_list", coll=coll))

        # prepare product data for form
        doc_json = to_json(obj)
        if obj.get("created_at") and isinstance(obj.get("created_at"), datetime):
            doc_json["created_at"] = obj.get("created_at").isoformat()
        if obj.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
            doc_json["updated_at"] = obj.get("updated_at").isoformat()
        return render_template("admin/product_form.html", coll=coll, cats=cats, doc=doc_json, admin=current_admin())
    if request.method == "POST":
        data = request.form.get("data")
        try:
            import json

            doc = json.loads(data)
        except Exception as e:
            flash(f"Invalid JSON: {e}", "danger")
            return render_template("admin/doc_form.html", coll=coll, data=data, doc=to_json(obj), admin=current_admin())
        # ensure we don't change the _id
        doc.pop("_id", None)
        db[coll].update_one({"_id": obj["_id"]}, {"$set": doc})
        flash("Document updated.", "success")
        return redirect(url_for("admin.docs_list", coll=coll))

    import json

    data = json.dumps(to_json(obj), indent=2)
    return render_template("admin/doc_form.html", coll=coll, data=data, doc=to_json(obj), admin=current_admin())


@admin_bp.route("/collections/<coll>/docs/<id>/delete", methods=["GET", "POST"])
@login_required
def docs_delete(coll, id):
    if coll not in ALLOWED_COLLECTIONS:
        flash("Collection not allowed.", "warning")
        return redirect(url_for("admin.collections_list"))
    db = get_db()
    obj = db[coll].find_one({"_id": ObjectId(id)})
    if not obj:
        flash("Document not found.", "warning")
        return redirect(url_for("admin.docs_list", coll=coll))

    if request.method == "POST":
        db[coll].delete_one({"_id": obj["_id"]})
        flash("Document deleted.", "info")
        return redirect(url_for("admin.docs_list", coll=coll))

    return render_template("admin/confirm_delete.html", user=to_json(obj), admin=current_admin())


@admin_bp.route("/collections/<coll>/docs/<id>/view")
@login_required
def docs_view(coll, id):
    """Show a single document; used for contact messages and generic view."""
    if coll not in ALLOWED_COLLECTIONS:
        flash("Collection not allowed.", "warning")
        return redirect(url_for("admin.collections_list"))
    db = get_db()
    obj = db[coll].find_one({"_id": ObjectId(id)})
    if not obj:
        flash("Document not found.", "warning")
        return redirect(url_for("admin.docs_list", coll=coll))

    doc = to_json(obj)
    # format datetimes for known fields
    if doc.get("created_at") and isinstance(obj.get("created_at"), datetime):
        doc["created_at"] = obj.get("created_at").isoformat()
    if doc.get("updated_at") and isinstance(obj.get("updated_at"), datetime):
        doc["updated_at"] = obj.get("updated_at").isoformat()

    # For products, resolve category name for nicer view
    if coll == PRODUCTS:
        cid = doc.get("category_id")
        if cid:
            try:
                cat_obj = get_db()[CATEGORIES].find_one({"_id": ObjectId(cid)})
            except Exception:
                # maybe stored as plain string id
                try:
                    cat_obj = get_db()[CATEGORIES].find_one({"_id": cid})
                except Exception:
                    cat_obj = None
            if cat_obj:
                doc["category_name"] = cat_obj.get("name")

    # If contact message, render a friendly view
    if coll == CONTACT_MESSAGES:
        # resolve product info if present
        pid = doc.get("product_id")
        if pid:
            try:
                prod = get_db()[PRODUCTS].find_one({"_id": ObjectId(pid)})
            except Exception:
                prod = get_db()[PRODUCTS].find_one({"_id": pid})
            if prod:
                doc["product_id"] = str(prod.get("_id"))
                doc["product_name"] = prod.get("name")
        return render_template("admin/contact_message_view.html", doc=doc, admin=current_admin())

    # If testimonial, render a friendly testimonial view
    if coll == TESTIMONIALS:
        return render_template("admin/testimonial_view.html", coll=coll, doc=doc, admin=current_admin())

    return render_template("admin/doc_view.html", coll=coll, doc=doc, admin=current_admin())
