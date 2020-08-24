from typing import Tuple

import numpy as np

from jina.drivers.helper import array2pb
from jina.drivers.search import VectorSearchDriver
from jina.executors.indexers import BaseVectorIndexer
from jina.proto import jina_pb2
from tests import JinaTestCase


class MockIndexer(BaseVectorIndexer):
    def add(self, keys: 'np.ndarray', vectors: 'np.ndarray', *args, **kwargs):
        pass

    def get_query_handler(self):
        pass

    def get_add_handler(self):
        pass

    def get_create_handler(self):
        pass

    def query(self, vectors: 'np.ndarray', top_k: int, *args, **kwargs) -> Tuple['np.ndarray', 'np.ndarray']:
        # vectors that will come are 1-D arrays with chunk ID value,
        # mock the indexer so that every chunk matches a chunk
        # with an id that is 100 * chunk.id, and an embedding of [chunk.id * 0.01]
        # so that the score can be asserted easily
        idx_top_1 = 100 * vectors[:]
        idx_top_2 = 1000 * vectors[:]
        idx = np.hstack((idx_top_1, idx_top_2))
        dist_top_1 = 0.01 * vectors[:]
        dist_top_2 = 0.1 * vectors[:]
        dist = np.hstack((dist_top_1, dist_top_2))
        return idx, dist


class SimpleVectorSearchDriver(VectorSearchDriver):

    @property
    def queryset(self):
        q = jina_pb2.QueryLang()
        q.name = 'SimpleVectorSearchDriver'
        q.priority = 1
        q.parameters['top_k'] = 4
        return [q]

    @property
    def exec_fn(self):
        return self._exec_fn


def create_document_to_search():
    # 1-D embedding
    # doc: 1 - chunk: 2 - embedding(2.0)
    #        - chunk: 3 - embedding(3.0)
    #        - chunk: 4 - embedding(4.0)
    #        - chunk: 5 - embedding(5.0)
    # ....
    doc = jina_pb2.Document()
    doc.id = 1
    for c in range(10):
        chunk = doc.chunks.add()
        chunk.id = doc.id + c + 1
        chunk.embedding.CopyFrom(array2pb(np.array([chunk.id])))
    return doc


class VectorSearchDriverTestCase(JinaTestCase):

    def test_vectorsearch_driver_mock_queryset(self):
        # no queryset
        driver = VectorSearchDriver(top_k=3)
        assert driver.top_k == 3

        # with queryset
        driver = SimpleVectorSearchDriver(top_k=3)
        assert driver.top_k == 4

    def test_vectorsearch_driver_mock_indexer(self):
        doc = create_document_to_search()
        driver = SimpleVectorSearchDriver(top_k=2)
        executor = MockIndexer()
        driver.attach(executor=executor, pea=None)
        driver._apply_all(doc.chunks)

        for chunk in doc.chunks:
            assert len(chunk.matches) == 2
            assert chunk.matches[0].id == chunk.id * 100
            assert chunk.matches[1].id == chunk.id * 1000
            assert chunk.matches[0].level_depth == chunk.level_depth
            assert chunk.matches[1].level_depth == chunk.level_depth
            assert chunk.matches[0].score.ref_id == chunk.id
            assert chunk.matches[1].score.ref_id == chunk.id
            self.assertAlmostEqual(chunk.matches[0].score.value, chunk.id * 0.01)
            self.assertAlmostEqual(chunk.matches[1].score.value, chunk.id * 0.1)
