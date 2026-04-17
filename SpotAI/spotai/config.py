from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    map_primary_provider: str = Field(default='naver', alias='MAP_PRIMARY_PROVIDER')
    map_fallback_provider: str = Field(default='kakao', alias='MAP_FALLBACK_PROVIDER')
    enable_mock_data: bool = Field(default=True, alias='ENABLE_MOCK_DATA')

    teams_webhook_url: str | None = Field(default=None, alias='TEAMS_WEBHOOK_URL')
    reservation_api_key: str | None = Field(default=None, alias='RESERVATION_API_KEY')
    kakao_map_api_key: str | None = Field(default=None, alias='KAKAO_MAP_API_KEY')
    kakao_map_js_key: str | None = Field(default=None, alias='KAKAO_MAP_JS_KEY')
    naver_search_client_id: str | None = Field(default=None, alias='NAVER_SEARCH_CLIENT_ID')
    naver_search_client_secret: str | None = Field(default=None, alias='NAVER_SEARCH_CLIENT_SECRET')
    naver_map_client_id: str | None = Field(default=None, alias='NAVER_MAP_CLIENT_ID')

    openai_api_key: str | None = Field(default=None, alias='OPENAI_API_KEY')
    openai_model: str = Field(default='gpt-4o-mini', alias='OPENAI_MODEL')
    rag_docs_dir: str = Field(default='spotai/knowledge', alias='RAG_DOCS_DIR')
    rag_top_k: int = Field(default=4, alias='RAG_TOP_K')

    tavily_api_key: str | None = Field(default=None, alias='TAVILY_API_KEY')

    use_mcp_tools: bool = Field(default=False, alias='USE_MCP_TOOLS')
    mcp_base_url: str | None = Field(default=None, alias='MCP_BASE_URL')
    mcp_search_path: str = Field(default='/tools/search', alias='MCP_SEARCH_PATH')
    mcp_reservation_path: str = Field(default='/tools/reservation', alias='MCP_RESERVATION_PATH')
    mcp_notify_path: str = Field(default='/tools/notify', alias='MCP_NOTIFY_PATH')


settings = Settings()
