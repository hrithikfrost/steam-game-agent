from types import SimpleNamespace

from app.services.recommendation_engine import RecommendationEngine


def test_disliked_tags_reduce_score():
    user = SimpleNamespace(
        preference=SimpleNamespace(
            preferred_tags={"rpg": 2.0, "story": 1.0},
            inferred_tags={},
            disliked_tags=["soulslike"],
            liked_games=[],
        )
    )
    good_game = SimpleNamespace(name="Good RPG", tags=["rpg", "story"], genres=[], rating=4.5)
    bad_game = SimpleNamespace(name="Hard RPG", tags=["rpg", "soulslike"], genres=[], rating=4.5)
    engine = RecommendationEngine(rawg=None, llm=None)

    assert engine._score_game(user, good_game) > engine._score_game(user, bad_game)

