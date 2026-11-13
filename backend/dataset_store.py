"""In-memory storage for uploaded datasets.

Before: the browser re-sent the whole CSV with every request and the server
re-parsed it each time. Now the CSV is parsed ONCE at upload, stored here, and
the browser only sends a small `dataset_id`.

Limits of this design (worth knowing for interviews): data lives in server
memory, so it disappears when the server restarts and is not shared between
multiple server processes. For a portfolio app that is a deliberate trade-off;
a production system would use a database or object storage instead.
"""

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import pandas as pd


@dataclass
class StoredDataset:
    dataset_id: str
    filename: str
    df: pd.DataFrame


class DatasetStore:
    def __init__(self, max_datasets: int = 20):
        self._items: "OrderedDict[str, StoredDataset]" = OrderedDict()
        self._max = max_datasets
        self._lock = threading.Lock()  # FastAPI runs sync endpoints in threads

    def add(self, df: pd.DataFrame, filename: str) -> StoredDataset:
        item = StoredDataset(uuid.uuid4().hex, filename, df)
        with self._lock:
            self._items[item.dataset_id] = item
            while len(self._items) > self._max:  # evict the oldest upload
                self._items.popitem(last=False)
        return item

    def get(self, dataset_id: str) -> StoredDataset | None:
        with self._lock:
            return self._items.get(dataset_id)


store = DatasetStore()
