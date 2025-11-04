import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")

def num_tokens_from_string(string: str, model_name: str = "cl100k_base") -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0