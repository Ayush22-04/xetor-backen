from flask import Flask

from app import create_app


class DummyColl:
	def __init__(self, docs):
		self._docs = docs

	def find(self, query=None):
		if query:
			# very small subset of pymongo-style matching used in tests
			key, val = next(iter(query.items()))
			return [d for d in self._docs if d.get(key) == val]
		return list(self._docs)


def test_collections_popular_endpoint_returns_categories_and_only_popular_products(monkeypatch):
	app = create_app()

	sample_categories = [{"_id": "c1", "name": "Cat 1"}, {"_id": "c2", "name": "Cat 2"}]
	sample_products = [
		{"_id": "p1", "name": "P1", "is_populer": True},
		{"_id": "p2", "name": "P2", "is_populer": False},
		{"_id": "p3", "name": "P3", "is_populer": True},
	]

	# Monkeypatch the module-level get_collection used by the API routes
	import app.api.routes as routes_mod

	def fake_get_collection(name):
		if name == "categories":
			return DummyColl(sample_categories)
		if name == "products":
			return DummyColl(sample_products)
		return None

	monkeypatch.setattr(routes_mod, "get_collection", fake_get_collection)

	client = app.test_client()
	resp = client.get("/api/collections/popular")
	assert resp.status_code == 200
	data = resp.get_json()
	assert "categories" in data and "products" in data
	assert len(data["categories"]) == 2
	# Only products with is_populer True should be returned
	assert {p["name"] for p in data["products"]} == {"P1", "P3"}


def test_categories_popular_endpoint_returns_only_popular_categories(monkeypatch):
	app = create_app()

	sample_categories = [
		{"_id": "c1", "name": "Cat 1", "is_populer": True},
		{"_id": "c2", "name": "Cat 2", "is_populer": False},
	]

	import app.api.routes as routes_mod

	def fake_get_collection(name):
		if name == "categories":
			return DummyColl(sample_categories)
		return None

	monkeypatch.setattr(routes_mod, "get_collection", fake_get_collection)

	client = app.test_client()
	resp = client.get("/api/categories/popular")
	assert resp.status_code == 200
	data = resp.get_json()
	assert isinstance(data, list)
	assert {c["name"] for c in data} == {"Cat 1"}


def test_products_popular_endpoint_returns_only_popular_products(monkeypatch):
	app = create_app()

	sample_products = [
		{"_id": "p1", "name": "P1", "is_populer": True},
		{"_id": "p2", "name": "P2", "is_populer": False},
		{"_id": "p3", "name": "P3", "is_populer": True},
	]

	import app.api.routes as routes_mod

	def fake_get_collection(name):
		if name == "products":
			return DummyColl(sample_products)
		return None

	monkeypatch.setattr(routes_mod, "get_collection", fake_get_collection)

	client = app.test_client()
	resp = client.get("/api/products/popular")
	assert resp.status_code == 200
	data = resp.get_json()
	assert {p["name"] for p in data} == {"P1", "P3"}

