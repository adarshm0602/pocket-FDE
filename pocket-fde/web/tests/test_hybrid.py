"""Verify long source passages and synonymous queries survive dense retrieval."""
import numpy as np

from web.hybrid import DenseChunks


class Encoder:
    max_seq_length = 128
    class tokenizer:
        @staticmethod
        def encode(text, **kwargs):
            return text.split()
        @staticmethod
        def decode(tokens, **kwargs):
            return " ".join(tokens)
    def encode(self, texts, **kwargs):
        return np.array([[1., 0.] if any(word in text for word in ["delayed", "slow"]) else [0., 1.] for text in texts])


def test_long_document_tail_and_synonym_query_remain_searchable():
    arm = DenseChunks(["filler " * 500 + "delayed responses", "Vector embedding configuration"], model=Encoder())
    assert arm.scores("slow service") == [1., 0.]
    assert len(arm.chunks("filler " * 500)) > 1
