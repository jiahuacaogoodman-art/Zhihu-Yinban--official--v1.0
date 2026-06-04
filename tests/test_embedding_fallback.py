from app.services.embedding_fallback import HashEmbeddingFunction


def test_encode_single_text_is_list_like_and_supports_tolist():
    embedding = HashEmbeddingFunction(dim=8)

    vector = embedding.encode("patient profile")

    assert isinstance(vector, list)
    assert hasattr(vector, "tolist")
    assert vector.tolist() == list(vector)
    assert len(vector) == 8


def test_encode_batch_is_list_like_and_supports_tolist():
    embedding = HashEmbeddingFunction(dim=8)

    matrix = embedding.encode(["patient profile", "care plan"])

    assert isinstance(matrix, list)
    assert hasattr(matrix, "tolist")
    assert len(matrix) == 2
    assert matrix.tolist() == [list(row) for row in matrix]


def test_chroma_call_and_embed_query_keep_tolist_compatibility():
    embedding = HashEmbeddingFunction(dim=8)

    matrix = embedding(["patient profile"])
    query_vector = embedding.embed_query("patient profile")

    assert matrix.tolist() == [list(matrix[0])]
    assert query_vector.tolist() == list(query_vector)
