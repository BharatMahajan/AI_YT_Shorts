from pipeline.topic_select import pick_by_scores


def test_picks_highest_score():
    scores = {"a": 5, "b": 9, "c": 3}
    assert pick_by_scores(scores, recent=[], cooldown=2) == "b"


def test_cooldown_penalizes_recent():
    scores = {"a": 10, "b": 9}
    # 'a' is on cooldown, so 'b' wins despite lower raw score
    assert pick_by_scores(scores, recent=["a"], cooldown=2) == "b"


def test_falls_back_when_all_penalized():
    scores = {"a": 4, "b": 7}
    # both recent → still returns the best raw score
    assert pick_by_scores(scores, recent=["a", "b"], cooldown=2) == "b"
