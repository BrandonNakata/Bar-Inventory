from playwright.sync_api import Playwright

def test_list_ingredients_returns_non_empty_list(playwright: Playwright):
    api = playwright.request.new_context(base_url="http://localhost:8000/")
    response = api.get("api/ingredients")
    assert response.status == 200
    ingredients = response.json()
    assert isinstance(ingredients, list)
    assert len(ingredients) > 0
    api.dispose() 