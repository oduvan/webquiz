"""Queue of answers that wait for the teacher's check (questions with ``manual_check: true``).

Teachers open the review page (``/review/``); each open page is a *client* here.
The queue hands every client at most one answer at a time:

- a client without an answer gets the oldest answer that no client shows, so
  teachers working together get different answers;
- when every waiting answer is already open on another client, the client waits.
  The teacher may ask to help (``take_shared``): the client then gets the answer
  open on the fewest clients (the oldest of those). Two teachers then see the
  same answer and the first verdict counts. This helps when a colleague's phone
  is lying on the desk with an answer on it;
- a client keeps its answer until it gives a verdict, the answer is decided on
  another client, or it disconnects. An answer is never swapped under the
  teacher's finger.

This module only keeps the order and the assignment. The server stores the
verdict and sends the messages.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReviewItem:
    """One answer that waits for a verdict."""

    review_id: str
    user_id: str
    question_id: int
    #: What the review page shows (never the student's name)
    public: Dict[str, Any]
    #: Server data the verdict updates (the stored answer, the CSV row)
    refs: Dict[str, Any] = field(default_factory=dict)


class ReviewQueue:
    def __init__(self):
        self.items: Dict[str, ReviewItem] = {}  # review_id -> item, oldest first
        self.clients: Dict[Any, Optional[str]] = {}  # client -> review_id it shows (None = waiting)
        self._next_id = 1

    @property
    def pending_count(self) -> int:
        return len(self.items)

    @property
    def reviewers(self) -> int:
        return len(self.clients)

    def add(self, user_id: str, question_id: int, public: Dict[str, Any], refs: Dict[str, Any]) -> ReviewItem:
        """Put an answer at the end of the queue and return its item."""
        review_id = str(self._next_id)
        self._next_id += 1
        item = ReviewItem(review_id, user_id, question_id, dict(public, review_id=review_id), refs)
        self.items[review_id] = item
        return item

    def connect(self, client) -> None:
        self.clients[client] = None

    def disconnect(self, client) -> None:
        self.clients.pop(client, None)

    def item_for(self, client) -> Optional[ReviewItem]:
        review_id = self.clients.get(client)
        return self.items.get(review_id) if review_id is not None else None

    def decide(self, review_id: str) -> Optional[ReviewItem]:
        """Take a decided answer out of the queue.

        Returns:
            The item, or None when it is not waiting any more (decided on
            another page, or the quiz was restarted).
        """
        item = self.items.pop(review_id, None)
        if item is None:
            return None
        for client, shown in self.clients.items():
            if shown == review_id:
                self.clients[client] = None
        return item

    def clear(self) -> None:
        """Forget every waiting answer (quiz switch or restart). Clients stay connected."""
        self.items.clear()
        for client in self.clients:
            self.clients[client] = None

    def assign_idle(self) -> List[Any]:
        """Give an answer to every client that has none, in connection order.

        Returns:
            The clients that got an answer.
        """
        changed = []
        for client, shown in self.clients.items():
            if shown is not None and shown in self.items:
                continue
            viewers = self._viewers()
            review_id = next((rid for rid, count in viewers.items() if count == 0), None)
            self.clients[client] = review_id
            if review_id is not None:
                changed.append(client)
        return changed

    def take_shared(self, client) -> bool:
        """Give a waiting client an answer that is open on other clients (the teacher asked to help).

        Returns:
            True when the client got an answer
        """
        if client not in self.clients or self.item_for(client) is not None:
            return False
        viewers = self._viewers()
        best = None
        for review_id, count in viewers.items():  # oldest first, so ties go to the oldest
            if best is None or count < viewers[best]:
                best = review_id
        self.clients[client] = best
        return best is not None

    def _viewers(self) -> Dict[str, int]:
        """Number of clients that show each waiting answer, oldest answer first."""
        viewers = {review_id: 0 for review_id in self.items}
        for shown in self.clients.values():
            if shown in viewers:
                viewers[shown] += 1
        return viewers
