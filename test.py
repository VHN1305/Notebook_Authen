import psycopg2

# Connection string bạn đã cung cấp
DB_URL = "postgresql://postgres:8/R5MsN67aS*57N@db.ymxusrhbakjqdgswdseh.supabase.co:5432/nsmo"

def list_tables():
    try:
        # 1. Kết nối đến database
        print("Đang kết nối đến Supabase...")
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # 2. Query lấy danh sách bảng (trừ các bảng hệ thống của Postgres)
        query = """
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name;
        """
        
        cur.execute(query)
        tables = cur.fetchall()

        # 3. In kết quả
        if not tables:
            print("\nKết nối thành công nhưng không tìm thấy bảng nào (Database rỗng).")
        else:
            print(f"\nKết nối thành công! Tìm thấy {len(tables)} bảng:")
            print("-" * 40)
            print(f"{'SCHEMA':<15} | {'TABLE NAME'}")
            print("-" * 40)
            for schema, name in tables:
                print(f"{schema:<15} | {name}")

        # Đóng kết nối
        cur.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ Lỗi kết nối: {e}")

if __name__ == "__main__":
    list_tables()