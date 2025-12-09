"""
Cloudflare R2 Storage Integration
Handles image uploads/downloads to Cloudflare R2 object storage
"""
import os
import boto3
from botocore.exceptions import ClientError
from io import BytesIO
import mimetypes
from dotenv import load_dotenv

load_dotenv()

# R2 Configuration
R2_ENDPOINT_URL = os.getenv('R2_ENDPOINT_URL')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME', 'reviewsite-images')
R2_PUBLIC_URL = os.getenv('R2_PUBLIC_URL')  # Optional custom domain

# Initialize S3 client for R2
s3_client = None

def get_r2_client():
    """Get or create S3 client configured for Cloudflare R2"""
    global s3_client

    if s3_client is None:
        if not all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
            raise ValueError(
                "R2 credentials not configured. Please set R2_ENDPOINT_URL, "
                "R2_ACCESS_KEY_ID, and R2_SECRET_ACCESS_KEY in .env"
            )

        s3_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name='auto'  # R2 uses 'auto' for region
        )

    return s3_client


def upload_file(file_path, r2_key, content_type=None):
    """
    Upload a file to R2

    Args:
        file_path: Local path to the file to upload
        r2_key: Key (path) in R2 bucket (e.g., 'covers/570_skyrim.png')
        content_type: MIME type (e.g., 'image/png'). Auto-detected if None.

    Returns:
        Public URL to the uploaded file, or None if upload failed
    """
    try:
        client = get_r2_client()

        # Auto-detect content type if not provided
        if content_type is None:
            # Try standard library guess first
            guessed, _ = mimetypes.guess_type(file_path)
            if guessed:
                content_type = guessed
            else:
                # Fallback to simple extension map for common image types
                ext = os.path.splitext(file_path)[1].lower()
                content_type_map = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.webp': 'image/webp',
                    '.gif': 'image/gif'
                }
                content_type = content_type_map.get(ext, 'application/octet-stream')

        # Upload file (R2 uses bucket-level public access, not object ACLs)
        with open(file_path, 'rb') as f:
            client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=r2_key,
                Body=f,
                ContentType=content_type
            )

        return get_public_url(r2_key)

    except ClientError as e:
        print(f"Error uploading {file_path} to R2: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error uploading to R2: {e}")
        return None


def upload_file_object(file_obj, r2_key, content_type=None):
    """
    Upload a file-like object to R2

    Args:
        file_obj: File-like object (from request.files or BytesIO)
        r2_key: Key (path) in R2 bucket
        content_type: MIME type

    Returns:
        Public URL to the uploaded file, or None if upload failed
    """
    try:
        client = get_r2_client()

        # Auto-detect content type if not provided
        if content_type is None:
            # If this is a Flask/Werkzeug FileStorage, it may have a useful mimetype
            file_mimetype = getattr(file_obj, 'mimetype', None)
            if file_mimetype:
                content_type = file_mimetype
            else:
                guessed, _ = mimetypes.guess_type(r2_key)
                if guessed:
                    content_type = guessed
                else:
                    ext = os.path.splitext(r2_key)[1].lower()
                    content_type_map = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.webp': 'image/webp',
                        '.gif': 'image/gif'
                    }
                    content_type = content_type_map.get(ext, 'application/octet-stream')

        # Reset file pointer to beginning
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

        # Upload file object (R2 uses bucket-level public access, not object ACLs)
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key,
            Body=file_obj,
            ContentType=content_type
        )

        return get_public_url(r2_key)

    except ClientError as e:
        print(f"Error uploading file object to R2: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error uploading to R2: {e}")
        return None


def download_to_file(r2_key, local_path):
    """
    Download a file from R2 to local filesystem

    Args:
        r2_key: Key (path) in R2 bucket
        local_path: Local path to save the file

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_r2_client()

        # Ensure directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Download file
        client.download_file(R2_BUCKET_NAME, r2_key, local_path)
        return True

    except ClientError as e:
        print(f"Error downloading {r2_key} from R2: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error downloading from R2: {e}")
        return False


def download_to_memory(r2_key):
    """
    Download a file from R2 to memory

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        BytesIO object containing file data, or None if download failed
    """
    try:
        client = get_r2_client()

        # Download to BytesIO
        file_obj = BytesIO()
        client.download_fileobj(R2_BUCKET_NAME, r2_key, file_obj)
        file_obj.seek(0)
        return file_obj

    except ClientError as e:
        print(f"Error downloading {r2_key} from R2 to memory: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error downloading from R2: {e}")
        return None


def file_exists(r2_key):
    """
    Check if a file exists in R2

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        True if file exists, False otherwise
    """
    try:
        client = get_r2_client()
        client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        print(f"Error checking if {r2_key} exists in R2: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error checking R2 file existence: {e}")
        return False


def delete_file(r2_key):
    """
    Delete a file from R2

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_r2_client()
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        return True
    except ClientError as e:
        print(f"Error deleting {r2_key} from R2: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error deleting from R2: {e}")
        return False


def get_public_url(r2_key):
    """
    Get the Flask backend URL for a file in R2

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        Flask route URL string (served through backend proxy)
    """
    # Return Flask backend route that will proxy the file from R2
    # This avoids needing public R2 access and gives full control
    return f"/r2/{r2_key}"


def list_files(prefix='', max_keys=1000):
    """
    List files in R2 bucket with optional prefix filter

    Args:
        prefix: Filter results to keys that begin with this prefix
        max_keys: Maximum number of keys to return

    Returns:
        List of file keys
    """
    try:
        client = get_r2_client()

        response = client.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=max_keys
        )

        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        return []

    except ClientError as e:
        print(f"Error listing files in R2: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error listing R2 files: {e}")
        return []


def get_etag(r2_key):
    """
    Get the ETag for a file in R2

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        ETag string, or None if file doesn't exist
    """
    try:
        client = get_r2_client()
        response = client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        return response.get('ETag', '').strip('"')
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        print(f"Error getting ETag for {r2_key}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error getting ETag from R2: {e}")
        return None


def get_content_type(r2_key):
    """
    Get the Content-Type for a file in R2

    Args:
        r2_key: Key (path) in R2 bucket

    Returns:
        Content-Type string, or None if not set / not found
    """
    try:
        client = get_r2_client()
        response = client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
        return response.get('ContentType')
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        print(f"Error getting Content-Type for {r2_key}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error getting Content-Type from R2: {e}")
        return None
