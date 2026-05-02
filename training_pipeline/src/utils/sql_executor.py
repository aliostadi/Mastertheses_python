import psycopg2
import os
from ..config.settings import DB_URL


class SQLExecutor:
    def __init__(self, db_url=None):
        self.db_url = db_url or DB_URL
    
    def _connect(self):
        """Create database connection"""
        return psycopg2.connect(self.db_url)
    
    def read_sql_file(self, sql_file_path):
        """Read SQL file content"""
        if not os.path.exists(sql_file_path):
            raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
        
        with open(sql_file_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    def execute_sql_file(self, sql_file_path, commit=True, fetch_results=False):
        """
        Execute SQL file
        
        Args:
            sql_file_path: Path to SQL file
            commit: Whether to commit the transaction
            fetch_results: Whether to return query results
        
        Returns:
            Query results if fetch_results=True, otherwise None
        """
        sql_content = self.read_sql_file(sql_file_path)
        return self.execute_sql(sql_content, commit, fetch_results)
    
    def execute_sql(self, sql_content, commit=True, fetch_results=False):
        """
        Execute SQL content
        
        Args:
            sql_content: SQL string to execute
            commit: Whether to commit the transaction
            fetch_results: Whether to return query results
        
        Returns:
            Query results if fetch_results=True, otherwise None
        """
        conn = None
        cur = None
        results = None
        
        try:
            conn = self._connect()
            cur = conn.cursor()
            
            # Split SQL content by semicolons for multiple statements
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            for statement in statements:
                print(f"Executing: {statement[:100]}..." if len(statement) > 100 else f"Executing: {statement}")
                cur.execute(statement)
                
                # Fetch results only for the last statement and if requested
                if fetch_results and statement == statements[-1]:
                    try:
                        results = cur.fetchall()
                        columns = [desc[0] for desc in cur.description] if cur.description else []
                        results = {'columns': columns, 'data': results}
                    except psycopg2.ProgrammingError:
                        # No results to fetch (e.g., CREATE TABLE)
                        results = None
            
            if commit:
                conn.commit()
                print("Transaction committed successfully")
            
            return results
            
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error executing SQL: {e}")
            raise
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def execute_sql_from_folder(self, folder_path, sql_filename):
        """
        Execute SQL file from a specific folder
        
        Args:
            folder_path: Path to folder containing SQL file
            sql_filename: Name of SQL file (with .sql extension)
        """
        sql_file_path = os.path.join(folder_path, sql_filename)
        return self.execute_sql_file(sql_file_path)