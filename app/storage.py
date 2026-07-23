from __future__ import annotations
import os
from pathlib import Path
from app.config import settings
import boto3 

class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, doc_id: str, filename: str, data: bytes) -> str:
        target = self.base / doc_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / filename
        path.write_bytes(data)
        return str(path)
    
    def load(self, path: str) -> bytes:
        return Path(path).read_bytes()
    
    def exists(self, path: str) -> bool:
        return Path(path).is_file()
    


class S3Storage:
 def __init__(self, bucket: str, region: str):
    self.bucket = bucket
    self.client = boto3.client("s3", region_name=region)
    self.prefix = "ledgerlens"

 def _key(self, path: str) -> str:
    return path.replace(f"s3://{self.bucket}/", "")
 
 def save(self, doc_id: str, filename: str, data: bytes) -> str:
    key = f"{self.prefix}/{doc_id}/{filename}"
    self.client.put_object(
        Bucket=self.bucket, Key=key, Body=data, ContentType="image/png"
    )
    return f"s3://{self.bucket}/{key}"
 
 def load(self, path: str) -> bytes:
    obj = self.client.get_object(Bucket=self.bucket, Key=self._key(path))
    return obj["Body"].read()
 
 def exists(self, path: str) -> bool:
    try:
        self.client.head_object(Bucket=self.bucket, Key=self._key(path))
        return True
    except Exception:
        return False



def get_storage():
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage(settings.S3_BUCKET, settings.AWS_REGION)
    return LocalStorage(settings.UPLOAD_DIR)