import concurrent.futures
from typing import List, Dict, Tuple
from src.core.recipe import DistroRecipe

class RecipeManager:
    def __init__(self):
        self._recipes: List[DistroRecipe] = []

    def register_recipe(self, recipe: DistroRecipe):
        self._recipes.append(recipe)

    def get_all_recipes(self) -> List[DistroRecipe]:
        return self._recipes

    def update_all(self, max_workers=10) -> Dict[str, Tuple[str, str, str]]:
        """
        Runs get_download_info for all recipes in parallel.
        Returns a dict: {RecipeName: (Version, URL, Hash)}
        Exceptions are returned as failure tuples in the version slot.
        """
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_recipe = {executor.submit(r.get_download_info): r for r in self._recipes}
            
            for future in concurrent.futures.as_completed(future_to_recipe):
                recipe = future_to_recipe[future]
                try:
                    info = future.result()
                    results[recipe.name] = info
                except Exception as exc:
                    results[recipe.name] = (f"ERROR: {str(exc)}", "", "")
        return results
