'''
storage.py -> Image Storage:
- LocalStorage: save, load, exists check
- S3Storage: key, save, load, exists check
- Switch b/w Loacl and AWS
'''

from __future__ import annotations
from pathlib import Path
from app.config import settings
import boto3 

#saving images to local storage: STORAGE_BACKEND=local
class LocalStorage:
    #makes base directory
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    #Writes image bytesin the folder
    def save(self, doc_id: str, filename: str, data: bytes) -> str:
        target = self.base / doc_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / filename
        path.write_bytes(data)
        return str(path)
    
    #reads the file in bytes
    def load(self, path: str) -> bytes:
        return Path(path).read_bytes()
    
    #checks if the file is present
    def exists(self, path: str) -> bool:
        return Path(path).is_file()
    

#saving images to local storage: STORAGE_BACKEND=s3
class S3Storage:
    #stores bucker name and initiallises things
    def __init__(self, bucket: str, region: str):
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)
        self.prefix = "onrecord"

    #helper as s3 objects are addressed by key
    def _key(self, path: str) -> str:
        return path.replace(f"s3://{self.bucket}/", "")
    
    #builds the key and uploads the bytes png to s3
    def save(self, doc_id: str, filename: str, data: bytes) -> str:
        key = f"{self.prefix}/{doc_id}/{filename}"
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType="image/png"
        )
        return f"s3://{self.bucket}/{key}"
    
    #reads the file in bytes via key
    def load(self, path: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
        return obj["Body"].read()
    
    #checks if the file is present through s3's metadata
    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(path))
            return True
        except Exception:
            return False


#switch between local and aws (s3) accordingly and choose the correct db
def get_storage():
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage(settings.S3_BUCKET, settings.AWS_REGION)
    return LocalStorage(settings.UPLOAD_DIR)