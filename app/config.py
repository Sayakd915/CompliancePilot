from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):

    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"

    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")

    supabase_bucket: str = "pdf_documents"

    mongodb_url: str = Field(..., env="MONGODB_URL")
    mongodb_db_name: str = "compliancepilot"    
    
    upstash_redis_rest_url: str = Field(..., env="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(..., env="UPSTASH_REDIS_REST_TOKEN")

    cache_ttl_seconds: int = 60 * 60 * 24 * 7

    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    app_env: str = "development"
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"

    langsmith_tracing: bool = True
    langsmith_endpoint: str = Field(..., env="LANGSMITH_ENDPOINT")
    langsmith_api_key: str = Field(..., env="LANGSMITH_API_KEY")
    langsmith_project: str = "compliancepilot"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True

    @property
    def origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()