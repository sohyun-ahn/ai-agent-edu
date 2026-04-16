from fastmcp import FastMCP

mcp = FastMCP("TextUtils")


@mcp.tool()
def count_chars(text: str) -> int:
    """주어진 텍스트의 글자 수(공백 포함)를 센다."""
    return len(text)


@mcp.tool()
def count_words(text: str) -> int:
    """주어진 텍스트의 단어 수를 센다 (공백 기준)."""
    return len(text.split())


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
