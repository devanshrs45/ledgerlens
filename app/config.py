'''
config.py -> Reads .env variables:
- Reads API Keys through dotenv
- Chooses vision and moderation model 
- Sets thresholds for review and moderation
- Sets Storage locations for Local and AWS
- Extimate Costs (Groq is free, so estimated using OpenAI Costs)
'''

from dotenv import load_dotenv
import os

load_dotenv()   #reads .env into the 

class Settings:
    #Groq AI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")   #Gets API Key
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")   #The address the request is sent to
    VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen/qwen3.6-27b")  #Specific model that reads the receipt (qwen)
    OUTPUT_FORMAT: str = os.getenv("OUTPUT_FORMAT", "json")   #json output

    #Moderation
    MODERATION_API_KEY: str = os.getenv("MODERATION_API_KEY", "")       #Default moderation for openai (as no moderation for groq)
    MODERATION_MODEL: str = os.getenv("MODERATION_MODEL", "omni-moderation-latest")
    MODERATION_SET: bool = os.getenv("MODERATION_SET", "false").lower() == "true"       #Off for groq / On with OpenAI Key

    #Thresholds
    REVIEW_THRESHOLD: float = float(os.getenv("REVIEW_THRESHOLD", "0.75"))      #Confidence threshold
    MODERATION_THRESHOLD: float = float(os.getenv("MODERATION_THRESHOLD", "0.5"))       #Content moderation

    #Hardcode the Cost Estimate for OPENAI API (For extendability - To Integrate OPENAI API in future)
    #Estimates using the tokens Groq used
    INPUT_TOKEN_COST: float = 0.0000025
    OUTPUT_TOKEN_COST: float = 0.00001

    #Image Handling
    IMAGE_DIM: int = int(os.getenv("IMAGE_DIM", "1024"))    #Max image size
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")        #image directory on local (for testing, ignored on AWS)

    #Storage
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./onrecord.db")      #To switch between aws and local - Records
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")        #To switch between aws and local - Images
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")         #Bucket name
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")     #Datacenter in Mumbai


    #API_BASE_URL: str = "http://localhost:8000"    #Connect to Streamlit UI. As I Did not use streamlitui later, this is not needed


settings = Settings()   #Instance for Settings