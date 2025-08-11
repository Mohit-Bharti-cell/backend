from db.supabase import supabase
from datetime import datetime

def delete_expired_tests():
    now = datetime.utcnow().isoformat()
    supabase.table("questions").delete().lt("expires_at", now).execute()
