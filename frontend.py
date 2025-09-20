import streamlit as st
import pandas as pd
import sys
import os
from datetime import date

try:
    import backend as db
except ImportError:
    st.error("Error: Could not import backend.py. Please ensure both frontend.py and backend.py are in the same directory.")
    st.stop()

# Initialize the database and tables
db.create_tables_and_insert_data()

st.set_page_config(layout="wide")
st.title("🎯 Performance Management System")
st.markdown("A simple tool to manage goals, track progress, and provide feedback.")

# ==============================================================================
# User Authentication (Simulated)
# ==============================================================================
st.sidebar.header("User Login")
users_df = db.get_users()
if users_df.empty:
    st.sidebar.error("No users found. Please check database.")
    st.stop()

user_names = users_df['name'].tolist()
selected_user_name = st.sidebar.selectbox("Select your name", user_names)
selected_user_info = users_df[users_df['name'] == selected_user_name].iloc[0]
user_id = int(selected_user_info['user_id'])
user_role = selected_user_info['role']

st.sidebar.success(f"Logged in as: {selected_user_name} ({user_role})")

# ==============================================================================
# Main Dashboard
# ==============================================================================
st.header("📊 Dashboard & Key Insights")
st.markdown("---")

metrics = db.get_dashboard_metrics(user_id, user_role)
if metrics:
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Goals", value=metrics['total_goals'])
    with col2:
        st.metric(label="Goals Completed", value=metrics['completed_goals'])
else:
    st.error("Could not load dashboard metrics.")

# ==============================================================================
# Goal & Progress Tracking
# ==============================================================================
st.header("📋 Goals & Progress Tracking")
st.markdown("---")

goals_df = db.get_goals(user_id, user_role)

if not goals_df.empty:
    st.subheader(f"{selected_user_name}'s Goals")
    st.dataframe(goals_df.drop('goal_id', axis=1), use_container_width=True)

    # ==============================================================================
    # Add Task & Update Goal Status
    # ==============================================================================
    st.subheader("Manage Goals & Tasks")
    
    col_task, col_status, col_feedback = st.columns(3)
    
    with col_task:
        st.subheader("Add Task to a Goal")
        with st.form("add_task_form"):
            selected_goal_id_task = st.selectbox(
                "Select a Goal",
                options=goals_df['goal_id'].tolist(),
                format_func=lambda x: goals_df[goals_df['goal_id'] == x]['title'].iloc[0],
                key="task_goal"
            )
            task_description = st.text_area("Task Description", key="task_desc")
            submitted_task = st.form_submit_button("Add Task")
            if submitted_task:
                if task_description:
                    db.add_task(selected_goal_id_task, task_description)
                    st.success("Task added successfully!")
                    st.experimental_rerun()
                else:
                    st.error("Task description is required.")
        
        st.subheader("Tasks for Selected Goal")
        if selected_goal_id_task:
            tasks_df = db.get_tasks_for_goal(selected_goal_id_task)
            st.dataframe(tasks_df.drop('task_id', axis=1), use_container_width=True)
            if tasks_df.empty:
                st.info("No tasks logged for this goal.")

    if user_role == 'Manager':
        with col_status:
            st.subheader("Update Goal Status")
            with st.form("update_status_form"):
                selected_goal_id_status = st.selectbox(
                    "Select a Goal",
                    options=goals_df['goal_id'].tolist(),
                    format_func=lambda x: goals_df[goals_df['goal_id'] == x]['title'].iloc[0],
                    key="status_goal"
                )
                new_status = st.selectbox("New Status", ['Draft', 'In Progress', 'Completed', 'Cancelled'], key="new_status")
                submitted_status = st.form_submit_button("Update Status")
                if submitted_status:
                    db.update_goal_status(selected_goal_id_status, new_status)
                    st.success("Goal status updated!")
                    st.experimental_rerun()
    
    with col_feedback:
        if user_role == 'Manager':
            st.subheader("Provide Feedback")
            with st.form("add_feedback_form"):
                selected_goal_id_feedback = st.selectbox(
                    "Select a Goal",
                    options=goals_df['goal_id'].tolist(),
                    format_func=lambda x: goals_df[goals_df['goal_id'] == x]['title'].iloc[0],
                    key="feedback_goal"
                )
                feedback_text = st.text_area("Feedback Text", key="feedback_text")
                submitted_feedback = st.form_submit_button("Add Feedback")
                if submitted_feedback:
                    if feedback_text:
                        employee_id = goals_df[goals_df['goal_id'] == selected_goal_id_feedback]['employee_id'].iloc[0]
                        db.add_feedback(selected_goal_id_feedback, user_id, employee_id, feedback_text)
                        st.success("Feedback submitted!")
                        st.experimental_rerun()
                    else:
                        st.error("Feedback text is required.")

else:
    st.info("No goals found for this user.")
    if user_role == 'Manager':
        st.write("You can set a new goal below.")

# ==============================================================================
# Goal & Reporting (Manager-only)
# ==============================================================================
if user_role == 'Manager':
    st.header("🎯 Set a New Goal")
    st.markdown("---")
    
    employees_df = db.get_employees()
    if not employees_df.empty:
        with st.form("set_goal_form"):
            goal_title = st.text_input("Goal Title")
            goal_description = st.text_area("Goal Description")
            goal_due_date = st.date_input("Due Date", date.today())
            selected_employee_id = st.selectbox(
                "Assign to Employee",
                options=employees_df['user_id'].tolist(),
                format_func=lambda x: employees_df[employees_df['user_id'] == x]['name'].iloc[0]
            )
            submitted = st.form_submit_button("Set Goal")
            if submitted:
                if goal_title:
                    db.add_goal(goal_title, goal_description, goal_due_date, user_id, selected_employee_id)
                    st.success("New goal created!")
                    st.experimental_rerun()
                else:
                    st.error("Goal title is required.")
    else:
        st.warning("No employees available to assign goals to.")

# ==============================================================================
# Performance History (Reporting)
# ==============================================================================
st.header("📜 Performance History")
st.markdown("---")

if user_role == 'Manager':
    employee_for_report_id = st.selectbox(
        "Select an Employee for Performance Report",
        options=employees_df['user_id'].tolist(),
        format_func=lambda x: employees_df[employees_df['user_id'] == x]['name'].iloc[0]
    )
    performance_data = db.get_performance_history(employee_for_report_id)
else:
    performance_data = db.get_performance_history(user_id)

if performance_data:
    st.subheader("Goals History")
    if not performance_data['goals'].empty:
        st.dataframe(performance_data['goals'].drop('goal_id', axis=1), use_container_width=True)
    else:
        st.info("No goals found in history.")

    st.subheader("Feedback History")
    if not performance_data['feedback'].empty:
        st.dataframe(performance_data['feedback'], use_container_width=True)
    else:
        st.info("No feedback found in history.")
