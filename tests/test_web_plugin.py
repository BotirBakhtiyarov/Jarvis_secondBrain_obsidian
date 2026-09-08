from orion.plugins.web_plugin import _flatten_topics, web_search


def test_web_search_requires_query():
    assert "error" in web_search("   ")


def test_flatten_topics_recurses():
    nested = [
        {"Text": "a", "FirstURL": "http://a"},
        {"Topics": [{"Text": "b", "FirstURL": "http://b"}]},
    ]
    out = []
    _flatten_topics(nested, out)
    assert [t["Text"] for t in out] == ["a", "b"]
