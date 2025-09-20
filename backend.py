import psycopg2
import pandas as pd
from typing import List, Dict, Any
import streamlit as st

# Replace with your actual database credentials
DB_HOST = "localhost"
DB_NAME = "ePMS"
DB_USER = "postgres"
DB_PASSWORD = "Harry#17"

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.OperationalError as e:
        st.error(f"Error connecting to database: {e}")
        return None

def create_tables_and_insert_data():
    """
    Creates the necessary tables for the PMS and inserts sample data.
    Includes a trigger for automated feedback.
    """
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor()
    try:
        cur.execute("""
            -- Users table to handle roles (Manager, Employee)
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('Manager', 'Employee'))
            );

            -- Goals table to store goals set by managers
            CREATE TABLE IF NOT EXISTS goals (
                goal_id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                due_date DATE,
                status VARCHAR(20) NOT NULL CHECK (status IN ('Draft', 'In Progress', 'Completed', 'Cancelled')),
                manager_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                employee_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE
            );

            -- Tasks table for employees to log tasks for goals
            CREATE TABLE IF NOT EXISTS tasks (
                task_id SERIAL PRIMARY KEY,
                goal_id INTEGER REFERENCES goals(goal_id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                is_approved BOOLEAN DEFAULT FALSE
            );

            -- Feedback table for managers to give feedback
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id SERIAL PRIMARY KEY,
                goal_id INTEGER REFERENCES goals(goal_id) ON DELETE CASCADE,
                manager_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                employee_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                feedback_text TEXT NOT NULL,
                feedback_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Trigger Function for automated feedback
        cur.execute("""
            CREATE OR REPLACE FUNCTION log_automated_feedback()
            RETURNS TRIGGER AS $$
            DECLARE
                goal_title TEXT;
            BEGIN
                IF NEW.status = 'Completed' AND OLD.status != 'Completed' THEN
                    SELECT title INTO goal_title FROM goals WHERE goal_id = NEW.goal_id;
                    INSERT INTO feedback (goal_id, manager_id, employee_id, feedback_text)
                    VALUES (
                        NEW.goal_id,
                        NEW.manager_id,
                        NEW.employee_id,
                        'Automated feedback: Goal "' || goal_title || '" has been marked as Completed. Great job!'
                    );
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            -- Trigger that fires when a goal's status is updated
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'goal_status_change') THEN
                    CREATE TRIGGER goal_status_change
                    AFTER UPDATE OF status ON goals
                    FOR EACH ROW
                    EXECUTE FUNCTION log_automated_feedback();
                END IF;
            END
            $$;
        """)

        # Insert sample data if tables are empty
        cur.execute("SELECT COUNT(*) FROM users;")
        if cur.fetchone()[0] == 0:
            sample_users = [
                ('Jane Doe', 'Manager'),
                ('John Smith', 'Employee'),
                ('Alice Johnson', 'Employee')
            ]
            cur.executemany("INSERT INTO users (name, role) VALUES (%s, %s);", sample_users)
            
            sample_goals = [
                ('Q3 Sales Target', 'Achieve 15% growth in Q3 sales.', '2025-09-30', 'In Progress', 1, 2),
                ('Complete Certification', 'Finish Python certification course.', '2025-08-31', 'Completed', 1, 3),
                ('Project A', 'Lead the new project from start to finish.', '2025-12-15', 'Draft', 1, 2)
            ]
            cur.executemany("INSERT INTO goals (title, description, due_date, status, manager_id, employee_id) VALUES (%s, %s, %s, %s, %s, %s);", sample_goals)
            
            conn.commit()
            print("Database tables and trigger created, and sample data inserted.")
        else:
            print("Database tables and data already exist. Skipping initialization.")

    except (Exception, psycopg2.Error) as error:
        st.error(f"Error creating tables or inserting data: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()

def get_users() -> pd.DataFrame:
    """Fetches all users for login and selection."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    query = "SELECT user_id, name, role FROM users ORDER BY name;"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_dashboard_metrics(user_id: int, role: str) -> Dict[str, Any]:
    """Calculates key metrics for the dashboard based on user role."""
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cur = conn.cursor()
        if role == 'Manager':
            cur.execute("SELECT COUNT(*) FROM goals WHERE manager_id = %s;", (user_id,))
            total_goals = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM goals WHERE manager_id = %s AND status = 'Completed';", (user_id,))
            completed_goals = cur.fetchone()[0]
        else:
            cur.execute("SELECT COUNT(*) FROM goals WHERE employee_id = %s;", (user_id,))
            total_goals = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM goals WHERE employee_id = %s AND status = 'Completed';", (user_id,))
            completed_goals = cur.fetchone()[0]
        
        metrics = {
            'total_goals': total_goals,
            'completed_goals': completed_goals
        }
        return metrics
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error fetching dashboard metrics: {error}")
        return {}
    finally:
        if conn:
            cur.close()
            conn.close()

def get_goals(user_id: int, role: str) -> pd.DataFrame:
    """Fetches goals based on the user's role."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    if role == 'Manager':
        query = """
            SELECT
                g.goal_id, g.title, g.description, g.due_date, g.status, u_emp.name AS employee_name
            FROM goals g
            JOIN users u_emp ON g.employee_id = u_emp.user_id
            WHERE g.manager_id = %s;
        """
        df = pd.read_sql(query, conn, params=(user_id,))
    else:
        query = """
            SELECT
                g.goal_id, g.title, g.description, g.due_date, g.status, u_mgr.name AS manager_name
            FROM goals g
            JOIN users u_mgr ON g.manager_id = u_mgr.user_id
            WHERE g.employee_id = %s;
        """
        df = pd.read_sql(query, conn, params=(user_id,))
    
    conn.close()
    return df

def add_goal(title: str, description: str, due_date: str, manager_id: int, employee_id: int):
    """Adds a new goal to the database."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO goals (title, description, due_date, status, manager_id, employee_id) VALUES (%s, %s, %s, %s, %s, %s);",
            (title, description, due_date, 'Draft', manager_id, employee_id)
        )
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error adding goal: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()

def update_goal_status(goal_id: int, status: str):
    """Updates the status of a goal (manager-only action)."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE goals SET status = %s WHERE goal_id = %s;",
            (status, goal_id)
        )
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error updating goal status: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()

def add_task(goal_id: int, description: str):
    """Adds a new task to a goal."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO tasks (goal_id, description) VALUES (%s, %s);",
            (goal_id, description)
        )
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error adding task: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()

def get_tasks_for_goal(goal_id: int) -> pd.DataFrame:
    """Fetches tasks for a specific goal."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    query = "SELECT task_id, description, is_approved FROM tasks WHERE goal_id = %s ORDER BY task_id;"
    df = pd.read_sql(query, conn, params=(goal_id,))
    conn.close()
    return df

def add_feedback(goal_id: int, manager_id: int, employee_id: int, feedback_text: str):
    """Adds written feedback for a goal."""
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO feedback (goal_id, manager_id, employee_id, feedback_text) VALUES (%s, %s, %s, %s);",
            (goal_id, manager_id, employee_id, feedback_text)
        )
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error adding feedback: {error}")
    finally:
        if conn:
            cur.close()
            conn.close()

def get_performance_history(employee_id: int) -> Dict[str, Any]:
    """
    Retrieves an employee's performance history including goals and feedback.
    """
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        goals_query = """
            SELECT
                g.goal_id, g.title, g.description, g.due_date, g.status, u.name AS manager_name
            FROM goals g
            JOIN users u ON g.manager_id = u.user_id
            WHERE g.employee_id = %s
            ORDER BY g.due_date DESC;
        """
        goals_df = pd.read_sql(goals_query, conn, params=(employee_id,))
        
        feedback_query = """
            SELECT
                f.feedback_date, f.feedback_text, u.name AS manager_name, g.title AS goal_title
            FROM feedback f
            JOIN users u ON f.manager_id = u.user_id
            JOIN goals g ON f.goal_id = g.goal_id
            WHERE f.employee_id = %s
            ORDER BY f.feedback_date DESC;
        """
        feedback_df = pd.read_sql(feedback_query, conn, params=(employee_id,))
        
        history = {
            'goals': goals_df,
            'feedback': feedback_df
        }
        return history
    except (Exception, psycopg2.Error) as error:
        st.error(f"Error fetching performance history: {error}")
        return {}
    finally:
        if conn:
            conn.close()

def get_employees() -> pd.DataFrame:
    """Fetches all employees for manager assignment."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    query = "SELECT user_id, name FROM users WHERE role = 'Employee' ORDER BY name;"
    df = pd.read_sql(query, conn)
    conn.close()
    return df
