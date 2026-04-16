from fastmcp import FastMCP

mcp = FastMCP("Math")
@mcp.tool()
def add(a: int, b: int) -> int:
    """두 정수를 더합니다."""
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """두 정수를 곱합니다."""
    return a * b


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)