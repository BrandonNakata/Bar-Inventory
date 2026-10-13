def test_list_ingredients_returns_non_empty_list(request_context):
    api = request_context
    response = api.get("api/ingredients")
    assert response.status == 200
    ingredients = response.json()
    assert isinstance(ingredients, list)
    assert len(ingredients) > 0
    