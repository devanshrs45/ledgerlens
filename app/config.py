from dotenv import load_dotenv
load_dotenv()

import os

class Settings:
    #Groq AI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")   #Gets API Key
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")   #The address the request is sent to
    VISION_MODEL: str = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")  #Specific model that reads the receipt
    STRUCTURED_OUTPUT_MODE: str = os.getenv("STRUCTURED_OUTPUT_MODE", "json")   #json output

    #Moderation
    MODERATION_API_KEY: str = os.getenv("MODERATION_API_KEY", "")       #Default groq moderation
    MODERATION_MODEL: str = os.getenv("MODERATION_MODEL", "omni-moderation-latest")
    MODERATION_ENABLED: bool = os.getenv("MODERATION_ENABLED", "false").lower() == "true"       #Off for groq

    #Thresholds
    REVIEW_THRESHOLD: float = float(os.getenv("REVIEW_THRESHOLD", "0.75"))      #Confidence threshold
    MODERATION_THRESHOLD: float = float(os.getenv("MODERATION_THRESHOLD", "0.5"))       #Content moderation

    #Cost Estimate for OPENAI API (For extendability - To Integrate OPENAI API in future)
    #Estimates using the tokens Groq used
    COST_PER_INPUT_TOKEN: float = float(os.getenv("COST_PER_INPUT_TOKEN", "0.0000025"))
    COST_PER_OUTPUT_TOKEN: float = float(os.getenv("COST_PER_OUTPUT_TOKEN", "0.00001"))

    #Image Handling
    MAX_IMAGE_DIM: int = int(os.getenv("MAX_IMAGE_DIM", "2048"))    #Max image size
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")        #image directory on local (for testing, ignored on AWS)

    #Storage
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./ledgerlens.db")      #To switch between aws and local - Records
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")        #To switch between aws and local - Images
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")         #Bucket name
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")     #Datacenter in Mumbai


    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")      #Connect to Streamlit UI


settings = Settings()