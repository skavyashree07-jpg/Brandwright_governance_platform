from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Brandwright API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql+psycopg2://localhost:5432/brandwright_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DEMO_MODE: str = "false"
    REVIEW_ASYNC: bool = False
    REVIEW_JOB_TIMEOUT_SECONDS: int = 300
    RETRIEVER: str = "memory"
    EMBEDDING_PROVIDER: str = "fake"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "brandwright"
    MINIO_SECURE: bool = False
    CORS_ORIGINS: str = "http://localhost:3000"
    LLM_MODE: str = "MOCK"
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

settings = Settings()
