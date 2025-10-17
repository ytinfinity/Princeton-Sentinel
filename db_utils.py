# db_utils.py
"""Shared database utilities for Princeton Insurance."""

import datetime
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)


def get_db_connection():
    """Get database connection."""
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        return psycopg2.connect(database_url)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


def insert_call_record(caller_phone, task_type, call_summary, detail_info):
    """Insert a call record into the database."""
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "Database connection failed"}

    try:
        now = datetime.datetime.now()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO post_call_analysis 
                (caller_phone, call_date, call_time, task_type, call_summary, detail_info)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    caller_phone,
                    now.date(),
                    now.time(),
                    task_type,
                    call_summary,
                    detail_info,
                ),
            )

            record_id = cur.fetchone()[0]
            conn.commit()
            print(f"[DB] Inserted call record ID: {record_id}", flush=True)
            return {"ok": True, "id": record_id}
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error inserting record: {e}", flush=True)
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def get_call_records(limit=10):
    """Get recent call records from the database."""
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, caller_phone, call_date, call_time, task_type, 
                       call_summary, detail_info, created_at
                FROM post_call_analysis
                ORDER BY created_at DESC
                LIMIT %s
            """,
                (limit,),
            )

            rows = cur.fetchall()
            records = []
            for row in rows:
                records.append(
                    {
                        "id": row[0],
                        "caller_phone": row[1],
                        "call_date": str(row[2]) if row[2] else None,
                        "call_time": str(row[3]) if row[3] else None,
                        "task_type": row[4],
                        "call_summary": row[5],
                        "detail_info": row[6],
                        "created_at": str(row[7]) if row[7] else None,
                    }
                )

            return {"ok": True, "records": records, "count": len(records)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()
