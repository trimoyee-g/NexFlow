import streamlit as st
import pandas as pd
import networkx as nx
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Streamlit configuration
st.set_page_config(page_title="NexFlow", layout="centered")

# Title
st.title("NexFlow: Synchronize Your Workflow!")
# st.subheader("")
st.write("A powerful task management tool that streamlines project workflows by tracking task dependencies, calculating schedules, and providing real-time status updates, ensuring that your team stays on track and meets deadlines.")

# Initialize session state for tasks and done status
if "tasks" not in st.session_state:
    st.session_state["tasks"] = []
if "done_tasks" not in st.session_state:
    st.session_state["done_tasks"] = set()  # Track names of completed tasks

# Function to add a task to session state
def add_task(task_name, duration, dependency):
    st.session_state["done_tasks"].discard(task_name)  # Reset done status if re-added
    st.session_state["tasks"].append({"task_name": task_name, "duration": duration, "dependency": dependency})

# Input section
st.subheader("Add Tasks with Dependencies")

# Streamlit form for adding tasks
with st.form("task_form"):
    task_name = st.text_input("Task Name")
    duration = st.number_input("Task Duration (in hours)", min_value=1)
    dependency = st.text_input("Dependency (optional, use task name)")
    submit_button = st.form_submit_button("Add Task")

    if submit_button and task_name:
        add_task(task_name, duration, dependency)
        st.success(f"Task '{task_name}' added successfully.")

# Topological sorting, status updates, and schedule calculation
def calculate_schedule(tasks):
    # Create a directed graph to represent tasks and dependencies
    G = nx.DiGraph()

    # Add tasks and durations as nodes
    for task in tasks:
        G.add_node(task["task_name"], duration=task.get("duration", 1))

    # Add dependencies as edges
    for task in tasks:
        if task["dependency"]:
            G.add_edge(task["dependency"], task["task_name"])

    # Check for cycles (to ensure dependencies do not form a loop)
    if not nx.is_directed_acyclic_graph(G):
        st.error("Cycle detected in dependencies. Please review your task dependencies.")
        return None

    # Perform topological sort to get the task execution order
    task_order = list(nx.topological_sort(G))

    # Calculate the start and end times based on dependencies
    schedule = []
    start_times = {}
    current_time = datetime.now()

    for task_name in task_order:
        node_data = G.nodes[task_name]
        duration = node_data.get("duration", 1)

        # Determine the earliest start time based on dependencies
        predecessors = list(G.predecessors(task_name))
        if predecessors:
            start_time = max(
                start_times[dep] + timedelta(hours=G.nodes[dep].get("duration", 1))
                for dep in predecessors
            )
        else:
            start_time = current_time

        end_time = start_time + timedelta(hours=duration)
        start_times[task_name] = start_time

        # Determine status based on current time and dependencies
        if task_name in st.session_state["done_tasks"]:
            status = "Completed"
            markable = False  # Already completed
        elif any(dep not in st.session_state["done_tasks"] for dep in predecessors):
            incomplete_deps = [dep for dep in predecessors if dep not in st.session_state["done_tasks"]]
            status = f"Waiting for {', '.join(incomplete_deps)} to be completed"
            markable = False  # Disable checkbox as dependencies are incomplete
        elif current_time < end_time:
            status = "In Progress"
            markable = True
        else:
            status = "Running Late"
            markable = True

        # Only add incomplete tasks to the schedule to display and Gantt chart
        if status != "Completed":
            schedule.append({
                "Task": task_name,
                "Start Time": start_time.strftime("%Y-%m-%d %H:%M"),
                "End Time": end_time.strftime("%Y-%m-%d %H:%M"),
                "Duration (hrs)": duration,
                "Status": status,
                "Markable": markable  # Keep track of whether the task is markable
            })

    return pd.DataFrame(schedule)

# Calculate schedule if tasks are added
if st.session_state["tasks"]:
    st.subheader("Calculated Schedule")
    schedule_df = calculate_schedule(st.session_state["tasks"])

    if schedule_df is not None:
        # Display schedule with checkboxes within the DataFrame
        checkboxes = []
        for _, row in schedule_df.iterrows():
            # Only enable the checkbox if the task is markable
            checkbox = st.checkbox(f"Mark {row['Task']} as done", key=f"{row['Task']}_done", value=(row["Task"] in st.session_state["done_tasks"]), disabled=not row["Markable"])
            if checkbox:
                st.session_state["done_tasks"].add(row["Task"])
            else:
                st.session_state["done_tasks"].discard(row["Task"])
            checkboxes.append(checkbox)

        # Add checkboxes to the DataFrame and display it
        schedule_df["Marked as Done"] = checkboxes

        # Only drop the "Markable" column if it exists in schedule_df
        def color_status(row):
            if row['Status'] == "In Progress":
                return f"<span style='color: green;'>{row['Status']}</span>"
            elif row['Status'] in ["Running late", "Delayed"]:
                return f"<span style='color: red;'>{row['Status']}</span>"
            else:
                return row['Status']

        # Apply the color function to the 'Status' column
        if not schedule_df.empty:
            if "Markable" in schedule_df.columns:
                schedule_df = schedule_df.drop(columns=["Markable"])

            # Apply color_status function and render HTML
            schedule_df['Status'] = schedule_df.apply(color_status, axis=1)
            st.write(schedule_df.to_html(escape=False), unsafe_allow_html=True)
        else:
            st.write("No tasks to display.")



        # Plot Gantt Chart for tasks that are not marked as completed
        st.subheader("Task Timeline")
        fig, ax = plt.subplots(figsize=(10, 5))

        for idx, row in schedule_df.iterrows():
            if row["Task"] not in st.session_state["done_tasks"]:
                start = datetime.strptime(row["Start Time"], "%Y-%m-%d %H:%M")
                end = datetime.strptime(row["End Time"], "%Y-%m-%d %H:%M")
                ax.barh(row["Task"], (end - start).total_seconds() / 3600, left=start.timestamp() / 3600, color="skyblue")
        # ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))  # Set tick intervals to 1 hour
        # ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))  # Format x-axis labels as 'HH:MM'
        ax.set_xlabel("Time (Hours)")
        ax.set_ylabel("Tasks")
        # ax.set_title("Gantt Chart for Task Schedule")
        ax.grid(axis="x", linestyle="--", color="gray", alpha=0.6)

        st.pyplot(fig)
