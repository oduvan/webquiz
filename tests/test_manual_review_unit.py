"""Unit tests for the queue that hands waiting answers to review pages."""

from webquiz.manual_review import ReviewQueue


def add(queue, answer):
    return queue.add("100001", 1, {"answer": answer}, {})


def shown(queue, client):
    item = queue.item_for(client)
    return item.public["answer"] if item else None


def test_review_ids_count_up_and_public_data_carries_the_id():
    queue = ReviewQueue()
    first = add(queue, "a")
    second = add(queue, "b")
    assert (first.review_id, second.review_id) == ("1", "2")
    assert first.public == {"answer": "a", "review_id": "1"}
    assert queue.pending_count == 2


def test_each_client_gets_a_different_answer_while_there_are_enough():
    queue = ReviewQueue()
    queue.connect("p1")
    queue.connect("p2")
    add(queue, "a")
    add(queue, "b")
    add(queue, "c")
    queue.assign_idle()
    assert (shown(queue, "p1"), shown(queue, "p2")) == ("a", "b")


def test_client_waits_when_every_answer_is_open_elsewhere():
    queue = ReviewQueue()
    queue.connect("p1")
    queue.connect("p2")
    queue.connect("p3")
    add(queue, "a")
    add(queue, "b")
    queue.assign_idle()
    assert [shown(queue, c) for c in ("p1", "p2", "p3")] == ["a", "b", None]


def test_answers_arriving_one_by_one_go_to_different_clients():
    queue = ReviewQueue()
    queue.connect("p1")
    queue.connect("p2")
    add(queue, "a")
    queue.assign_idle()
    add(queue, "b")
    queue.assign_idle()
    assert (shown(queue, "p1"), shown(queue, "p2")) == ("a", "b")


def test_take_shared_gives_the_answer_open_on_fewest_clients():
    queue = ReviewQueue()
    for client in ("p1", "p2", "p3", "p4"):
        queue.connect(client)
    add(queue, "a")
    add(queue, "b")
    queue.assign_idle()
    assert queue.take_shared("p3") is True
    assert shown(queue, "p3") == "a"
    assert queue.take_shared("p4") is True
    assert shown(queue, "p4") == "b"
    # A client that already shows an answer keeps it
    assert queue.take_shared("p1") is False
    assert shown(queue, "p1") == "a"


def test_take_shared_with_nothing_waiting():
    queue = ReviewQueue()
    queue.connect("p1")
    assert queue.take_shared("p1") is False
    assert shown(queue, "p1") is None


def test_a_shown_answer_is_never_swapped():
    queue = ReviewQueue()
    queue.connect("p1")
    add(queue, "a")
    queue.assign_idle()
    add(queue, "b")
    assert queue.assign_idle() == []
    assert shown(queue, "p1") == "a"


def test_decide_frees_every_client_showing_it():
    queue = ReviewQueue()
    queue.connect("p1")
    queue.connect("p2")
    item = add(queue, "a")
    queue.assign_idle()
    queue.take_shared("p2")
    assert shown(queue, "p2") == "a"
    assert queue.decide(item.review_id) is item
    assert shown(queue, "p1") is None and shown(queue, "p2") is None
    assert queue.decide(item.review_id) is None


def test_answer_of_a_closed_client_goes_to_a_waiting_one():
    queue = ReviewQueue()
    queue.connect("p1")
    add(queue, "a")
    queue.assign_idle()
    queue.connect("p2")
    queue.disconnect("p1")
    assert queue.assign_idle() == ["p2"]
    assert shown(queue, "p2") == "a"
    assert queue.reviewers == 1


def test_clear_keeps_clients_and_drops_answers():
    queue = ReviewQueue()
    queue.connect("p1")
    add(queue, "a")
    queue.assign_idle()
    queue.clear()
    assert queue.pending_count == 0
    assert queue.reviewers == 1
    assert shown(queue, "p1") is None
    assert add(queue, "b").review_id == "2"


def test_failed_csv_rewrite_is_tried_again_at_next_flush(tmp_path):
    import asyncio

    from webquiz.config import WebQuizConfig
    from webquiz.server import TestingServer

    server = TestingServer(WebQuizConfig())
    server.all_responses = [
        {
            "user_id": "100001",
            "question": "Q",
            "selected_answer": "a",
            "correct_answer": "",
            "is_correct": True,
            "time_taken_seconds": 1,
        }
    ]
    server.csv_rewrite_needed = True
    # The folder does not exist, so the write fails
    server.csv_file = str(tmp_path / "missing" / "quiz_0001.csv")
    try:
        asyncio.run(server.flush_responses_to_csv())
    except OSError:
        pass
    assert server.csv_rewrite_needed is True

    server.csv_file = str(tmp_path / "quiz_0001.csv")
    asyncio.run(server.flush_responses_to_csv())
    assert server.csv_rewrite_needed is False
    assert (tmp_path / "quiz_0001.csv").read_text(encoding="utf-8").splitlines()[1] == "100001,Q,a,,True,1"
