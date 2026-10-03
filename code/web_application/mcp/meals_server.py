import logging
import sys
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP


# ============================================================
# LOGGING
# ============================================================

# MCP STDIO uses stdout for JSON-RPC communication.
# Therefore, application logs must go to stderr.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("meals-server")


# ============================================================
# SERVER CONFIGURATION
# ============================================================

API_BASE = "https://www.themealdb.com/api/json/v1/1"

mcp = FastMCP(
    name="meals",
)


# ============================================================
# HTTP HELPER
# ============================================================

def get_json(endpoint: str) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint}"

    logger.info("Calling TheMealDB endpoint: %s", endpoint)

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException as exc:
        logger.error("TheMealDB request timed out")
        raise RuntimeError(
            "TheMealDB request timed out"
        ) from exc

    except httpx.HTTPError as exc:
        logger.error("TheMealDB HTTP request failed: %s", exc)
        raise RuntimeError(
            "TheMealDB request failed"
        ) from exc

    except ValueError as exc:
        logger.error("TheMealDB returned invalid JSON")
        raise RuntimeError(
            "TheMealDB returned invalid JSON"
        ) from exc


def validate_limit(
    limit: int,
    maximum: int,
):
    if limit < 1 or limit > maximum:
        raise ValueError(
            f"limit must be between 1 and {maximum}"
        )


def meal_card(
    meal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "area": meal.get("strArea"),
        "category": meal.get("strCategory"),
        "thumb": meal.get("strMealThumb"),
    }


def ingredient_card(
    meal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "thumb": meal.get("strMealThumb"),
    }


def full_meal_details(
    meal: dict[str, Any],
) -> dict[str, Any]:
    ingredients = []

    for number in range(1, 21):
        ingredient = meal.get(
            f"strIngredient{number}"
        )
        measure = meal.get(
            f"strMeasure{number}"
        )

        if ingredient and ingredient.strip():
            ingredients.append(
                {
                    "name": ingredient.strip(),
                    "measure": (measure or "").strip(),
                }
            )

    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": meal.get("strInstructions"),
        "image": meal.get("strMealThumb"),
        "source": meal.get("strSource"),
        "youtube": meal.get("strYoutube"),
        "ingredients": ingredients,
    }


def get_first_meal(
    payload: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    meals = payload.get("meals")

    if not meals:
        raise ValueError(message)

    return meals[0]


# ============================================================
# MCP TOOL 1: SEARCH BY NAME
# ============================================================

@mcp.tool()
def search_meals_by_name(
    query: str,
    limit: int = 5,
) -> Any:
    """
    Search TheMealDB meals by name.

    Args:
        query: Meal name or search text.
        limit: Number of results from 1 to 25.
    """
    query = query.strip()

    if not query:
        raise ValueError("query cannot be empty")

    validate_limit(limit, 25)

    encoded_query = quote(
        query,
        safe="",
    )

    payload = get_json(
        f"search.php?s={encoded_query}"
    )

    meals = payload.get("meals")

    if not meals:
        return {
            "results": [],
            "message": "no matches",
        }

    return [
        meal_card(meal)
        for meal in meals[:limit]
    ]


# ============================================================
# MCP TOOL 2: SEARCH BY INGREDIENT
# ============================================================

@mcp.tool()
def meals_by_ingredient(
    ingredient: str,
    limit: int = 12,
) -> Any:
    """
    Find meals by main ingredient.

    Args:
        ingredient: Main ingredient, such as chicken.
        limit: Number of results from 1 to 25.
    """
    ingredient = ingredient.strip()

    if not ingredient:
        raise ValueError(
            "ingredient cannot be empty"
        )

    validate_limit(limit, 25)

    encoded_ingredient = quote(
        ingredient,
        safe="",
    )

    payload = get_json(
        f"filter.php?i={encoded_ingredient}"
    )

    meals = payload.get("meals")

    if not meals:
        return {
            "results": [],
            "message": "no matches",
        }

    return [
        ingredient_card(meal)
        for meal in meals[:limit]
    ]


# ============================================================
# MCP TOOL 3: RANDOM MEAL
# ============================================================

@mcp.tool()
def random_meal() -> dict[str, Any]:
    """
    Retrieve one random meal from TheMealDB.
    """
    payload = get_json("random.php")

    meal = get_first_meal(
        payload,
        "No random meal was returned",
    )

    return full_meal_details(meal)


# ============================================================
# MCP TOOL 4: MEAL DETAILS
# ============================================================

@mcp.tool()
def meal_details(
    id: str | int,
) -> dict[str, Any]:
    """
    Retrieve full recipe details by meal ID.

    Args:
        id: TheMealDB meal ID.
    """
    meal_id = str(id).strip()

    if not meal_id.isdigit():
        raise ValueError(
            "id must be numeric"
        )

    payload = get_json(
        f"lookup.php?i={meal_id}"
    )

    meal = get_first_meal(
        payload,
        f"No meal found for id {meal_id}",
    )

    return full_meal_details(meal)


# ============================================================
# STDIO ENTRY POINT
# ============================================================

if __name__ == "__main__":
    logger.info(
        "Starting TheMealDB MCP server over STDIO"
    )

    mcp.run(
        transport="stdio"
    )