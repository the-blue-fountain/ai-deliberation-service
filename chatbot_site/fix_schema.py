#!/usr/bin/env python
"""Fix database schema for GraderResponse table"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot_site.settings')
django.setup()

from django.db import connection

def fix_schema():
    cursor = connection.cursor()
    
    # Add created_at column if it doesn't exist
    add_created_at = """
        ALTER TABLE core_graderresponse 
        ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
    """
    
    update_created_at = """
        UPDATE core_graderresponse 
        SET created_at = submitted_at 
        WHERE created_at IS NULL;
    """
    
    operations = [
        ("Adding created_at column", add_created_at),
        ("Updating created_at for existing rows", update_created_at),
    ]
    
    for op_name, sql in operations:
        try:
            cursor.execute(sql)
            print(f"✓ {op_name}")
        except Exception as e:
            if "already exists" in str(e):
                print(f"✓ {op_name} - already done")
            else:
                print(f"Note: {op_name} - {e}")
    
    cursor.close()
    print("\nDatabase schema fixed!")

if __name__ == '__main__':
    fix_schema()
