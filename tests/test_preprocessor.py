from datetime import datetime, timezone
from storage.models import Article
from core.preprocessor import Preprocessor

def make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test", "url": "https://example.com/1", "source": "Src",
        "published_at": datetime(2026, 4, 8, tzinfo=timezone.utc), "content": "", "language": "zh",
    }
    defaults.update(kwargs)
    return Article(**defaults)

def test_level1_sufficient_metadata():
    long_content = "这是一篇很长的文章描述。" * 20
    article = make_article(content=long_content)
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == long_content

def test_level2_structural_extraction():
    html_content = """
    <h1>Main Title</h1>
    <p>First important paragraph about the topic.</p>
    <p>Second paragraph with more details.</p>
    <h2>Key Point One</h2>
    <p>Details about key point one.</p>
    <h2>Key Point Two</h2>
    <p>Details about key point two.</p>
    <p>Final conclusion paragraph.</p>
    """
    article = make_article(content=html_content)
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert "First important paragraph" in result
    assert "Second paragraph" in result
    assert "Key Point One" in result
    assert "Key Point Two" in result
    assert "Final conclusion" in result

def test_short_plain_text_returned_as_is():
    article = make_article(content="Short text.")
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == "Short text."

def test_empty_content():
    article = make_article(content="")
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == ""
