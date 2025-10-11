import os
import mimetypes
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from supabase import create_client


# ✅ Use Django settings instead of direct os.getenv (keeps configuration consistent)
SUPABASE_URL = getattr(settings, "SUPABASE_URL", None)
SUPABASE_KEY = getattr(settings, "SUPABASE_SERVICE_KEY", None) or getattr(settings, "SUPABASE_KEY", None)
SUPABASE_BUCKET = getattr(settings, "SUPABASE_BUCKET", "learnora-media")

# Initialize Supabase client once
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupabaseStorage(Storage):
    """Custom Django storage backend using Supabase Storage."""

    def _open(self, name, mode="rb"):
        """Download file from Supabase."""
        clean_name = name.lstrip("/")
        res = supabase.storage.from_(SUPABASE_BUCKET).download(clean_name)
        if hasattr(res, "error") and res.error is not None:
            raise Exception(f"Supabase download failed: {res.error.message}")
        return ContentFile(res)

    def _save(self, name, content):
        """Upload file to Supabase."""
        file_bytes = content.read()

        # Detect content type
        content_type, _ = mimetypes.guess_type(name)
        options = {
            "cache-control": "3600",  # 1 hour cache
            "upsert": "true"          # must be string
        }
        if content_type:
            options["content-type"] = content_type

        clean_name = name.lstrip("/")

        # Upload file
        res = supabase.storage.from_(SUPABASE_BUCKET).upload(clean_name, file_bytes, options)

        if hasattr(res, "error") and res.error is not None:
            raise Exception(f"Supabase upload failed: {res.error.message}")

        return clean_name

    def delete(self, name):
        """Delete file from Supabase."""
        clean_name = name.lstrip("/")
        res = supabase.storage.from_(SUPABASE_BUCKET).remove([clean_name])
        if hasattr(res, "error") and res.error is not None:
            raise Exception(f"Supabase delete failed: {res.error.message}")

    def exists(self, name):
        """Check if file exists in Supabase."""
        clean_name = name.lstrip("/")
        res = supabase.storage.from_(SUPABASE_BUCKET).list()
        if hasattr(res, "error") and res.error is not None:
            raise Exception(f"Supabase list failed: {res.error.message}")
        return any(f["name"] == clean_name for f in res)

    def url(self, name):
        """Get public or signed URL depending on bucket visibility."""
        clean_name = name.lstrip("/")
        try:
            # First try public URL (works if bucket is public)
            return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(clean_name)
        except Exception:
            # Fallback to signed URL if bucket is private
            response = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(clean_name, 3600)
            return response.get("signedURL") if isinstance(response, dict) else response
