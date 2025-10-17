from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv(override=True)


def get_db_connection():
    """Establish database connection using DATABASE_URL environment variable."""
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def clean_database(conn):
    """Drop all existing tables in the database."""
    print("Cleaning database...")

    with conn.cursor() as cur:
        # Get all table names in the public schema
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """)

        tables = cur.fetchall()

        if not tables:
            print("  No tables found to drop.")
        else:
            print(f"  Found {len(tables)} table(s) to drop:")

            # Drop all tables with CASCADE to handle dependencies
            for (table_name,) in tables:
                try:
                    cur.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                            sql.Identifier(table_name)
                        )
                    )
                    print(f"    Dropped table: {table_name}")
                except Exception as e:
                    print(f"    Error dropping {table_name}: {e}")

        conn.commit()

    print("Database cleaned successfully.\n")


def create_tables(conn):
    """Create the post_call_analysis table."""
    print("Creating table...")

    with conn.cursor() as cur:
        # Post Call Analysis Table (simplified)
        cur.execute("""
            CREATE TABLE post_call_analysis (
                id SERIAL PRIMARY KEY,
                caller_phone VARCHAR(20) NOT NULL,
                call_date DATE NOT NULL,
                call_time TIME,
                task_type VARCHAR(100),
                call_summary TEXT,
                detail_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  Created table: post_call_analysis")

        # Create indexes for common query fields
        print("\nCreating indexes...")

        cur.execute("""
            CREATE INDEX idx_caller_phone ON post_call_analysis (caller_phone)
        """)
        print("  Created index: idx_caller_phone")

        cur.execute("""
            CREATE INDEX idx_call_date ON post_call_analysis (call_date)
        """)
        print("  Created index: idx_call_date")

        conn.commit()

    print("\nTable created successfully!")


def run_migration():
    """Main migration function."""
    print("=" * 50)
    print("Starting Database Migration")
    print("=" * 50 + "\n")

    conn = get_db_connection()

    try:
        clean_database(conn)
        create_tables(conn)

        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)

    except Exception as e:
        print(f"\nError during migration: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
