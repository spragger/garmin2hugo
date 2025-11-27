"""
Garmin-2-Hugo
Automates Hugo blog posts from Garmin activities.

This script runs as a menu-driven application.

Dependencies:
    pip install garminconnect python-dotenv tabulate python-dateutil requests

Environment Variables:
    GARMIN_EMAIL
    GARMIN_PASSWORD
"""

import logging
import os
import re
import subprocess
import sys
from dotenv import load_dotenv
from datetime import datetime
from getpass import getpass
from pathlib import Path
from tabulate import tabulate
from dateutil import parser as dtparser

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# ─────────────────────────────────────────────
# ── Logging Setup ────────────────────────────
# ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# ── Authentication & API ─────────────────────
# ─────────────────────────────────────────────


def init_api(email, password):
    """Initialize Garmin API session."""
    try:
#        print_banner()
        print("🔑 Logging in with Garmin credentials...\n")

        garmin = Garmin(email, password)
        try:
            garmin.login()
        except GarminConnectAuthenticationError as err:
            if "mfa" in str(err).lower():
                mfa_code = input("MFA one-time code: ")
                garmin.submit_mfa(mfa_code)
            else:
                raise

        print("✅ Successfully logged in.\n")
        return garmin

    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    ) as err:
        logger.error(err)
        sys.exit(f"❌ Garmin API initialization failed: {err}")


def print_banner():
    ascii_banner = r"""
  ++--------------------------------------------------------------------++
  ||                                                                    ||
  ||                            _        ____  _   _                    ||
  ||   __ _  __ _ _ __ _ __ ___ (_)_ __ |___ \| | | |_   _  __ _  ___   ||
  ||  / _` |/ _` | '__| '_ ` _ \| | '_ \  __) | |_| | | | |/ _` |/ _ \  ||
  || | (_| | (_| | |  | | | | | | | | | |/ __/|  _  | |_| | (_| | (_) | ||
  ||  \__, |\__,_|_|  |_| |_| |_|_|_| |_|_____|_| |_|\__,_|\__, |\___/  ||
  ||  |___/                                                 |___/       ||
  ||                                                                    ||
  ||     A python script to automate Hugo posts from Garmin activities  ||
  ||                                                                    ||
  ++--------------------------------------------------------------------++
"""
    GREEN = "\033[92m"
    RESET = "\033[0m"
    print(f"{GREEN}{ascii_banner}{RESET}")


# ─────────────────────────────────────────────
# ── Activity Selection ───────────────────────
# ─────────────────────────────────────────────


def display_and_select_activity(api):
    """Displays 10 recent activities and prompts user for selection by index."""
    print("\n📅 Fetching 10 Recent Garmin Activities...\n")
    try:
        activities = api.get_activities(0, 10)
    except Exception as e:
        print(f"❌ Error fetching activities: {e}")
        return None

    if not activities:
        print("⚠️ No recent activities found.")
        return None

    table = []
    for idx, act in enumerate(activities):
        name = act.get("activityName", "No Name")
        start_str = act.get("startTimeLocal", "Unknown Time")
        # Parse the datetime string to format it nicely
        try:
            start_dt = dtparser.parse(start_str)
            start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            start_formatted = start_str

        dist = round(act.get("distance", 0) * 0.000621371, 2)
        table.append([idx, start_formatted, name, f"{dist:.2f} mi"])

    headers = ["Index", "Date", "Activity", "Distance"]
    print(tabulate(table, headers, tablefmt="github"))

    while True:
        choice = input("\nSelect an activity by Index (or 'q' to quit to menu): ").strip()
        if choice.lower() == 'q':
            return None  # User cancellation

        if choice.isdigit():
            index = int(choice)
            if 0 <= index < len(activities):
                print(f"✅ Selected activity: {activities[index].get('activityName')}")
                return activities[index]  # Success
            else:
                print(f"❌ Invalid index. Please enter a number between 0 and {len(activities) - 1}.")
        else:
            print("❌ Invalid input. Please enter a number.")


# ─────────────────────────────────────────────
# ── User Input ───────────────────────────────
# ─────────────────────────────────────────────


def get_post_details():
    """Prompts user for post name and tags."""
    print("\n--- Post Details ---")
    post_name = ""
    while not post_name:
        post_name = input("Enter the post name (summary): ").strip()
        if not post_name:
            print("⚠️ Post name cannot be empty.")

    tags_input = input("Enter tags (comma-separated, or leave blank): ").strip()
    
    if not tags_input:
        return post_name, []  # Return empty list for no tags

    # Split and strip whitespace from each tag
    tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
    return post_name, tags_list


# ─────────────────────────────────────────────
# ── Data Parsing ─────────────────────────────
# ─────────────────────────────────────────────


def calculate_duration_and_pace(distance_mi, duration_sec):
    if distance_mi == 0:
        raise ValueError("Distance is zero, cannot calculate pace.")

    hour = int(duration_sec // 3600)
    minute = int((duration_sec % 3600) // 60)
    second = int(duration_sec % 60)

    duration_str = (
        f"{hour}:{minute:02}:{second:02}" if hour else f"{minute}:{second:02}"
    )

    pace_sec_per_mile = duration_sec / distance_mi
    pace_min = int(pace_sec_per_mile // 60)
    pace_sec = int(round(pace_sec_per_mile % 60))
    pace_str = f"{pace_min}:{pace_sec:02}"

    return duration_str, pace_str


def parse_notes(notes):
    m = re.search(r"w:(?P<workout>.+)\nc:(?P<comment>.+)", notes, flags=re.M | re.S)
    if not m:
        raise ValueError("Notes are missing required 'w: ...' (workout) or 'c: ...' (comment) fields.")
    return m.group("workout").strip(), m.group("comment").strip()


# ─────────────────────────────────────────────
# ── Markdown Post Writer ─────────────────────
# ─────────────────────────────────────────────


def write_post(activity, post_name, tags_list, output_dir, dry_run):
    """Writes the Hugo markdown file for the given activity."""
    try:
        start_date = dtparser.parse(activity.get("startTimeLocal", "")).date().isoformat()
        title = activity.get("activityName", "Untitled")

        distance = round(activity["distance"] * 0.000621371, 2)
        duration = activity["duration"]

        duration_str, pace_str = calculate_duration_and_pace(distance, duration)

        workout, comment = parse_notes(activity.get("description", ""))

        filename_title = re.sub(r"[^\w\-]+", "-", title.strip().lower())
        post_path = output_dir / f"{start_date}-{filename_title}.md"

        tags_formatted = ", ".join(f'"{t}"' for t in tags_list)

        frontmatter = f"""---
title: "{title}"
summary: "{post_name}"
date: {start_date} {datetime.now().strftime("%H:%M:%S")}
categories: post
tags: [{tags_formatted}]
---
```
{post_name} 
{distance:.2f} mi 
{duration_str} 
{pace_str}/mi 
Workout: {workout} 
Comments: {comment}
```
"""

        if dry_run:
            print(f"\n[DRY RUN] Would write to: {post_path}")
            print(frontmatter)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            with post_path.open("w") as f:
                f.write(frontmatter)
            print(f"✅ Post written to: {post_path}")
            subprocess.call("hugo --destination ~/html --templateMetrics", shell=True)
            print("✅ Hugo build command executed.")

    except (ValueError, KeyError, TypeError) as e:
        print(f"\n❌ Error processing post data: {e}")
        print("Post creation aborted.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during file writing: {e}")
        print("Post creation aborted.")


# ─────────────────────────────────────────────
# ── Application Flow ─────────────────────────
# ─────────────────────────────────────────────


def print_main_menu():
    """Prints the main menu options inside a banner and returns the user's choice."""
    GREEN = "\033[92m"
    RESET = "\033[0m"
    
    menu_banner = r"""
  ++--------------------------------------------------------------------++
  ||                                                                    ||
  ||                             _       ____  _   _                    ||
  ||   __ _  __ _ _ __ _ __ ___ (_)_ __ |___ \| | | |_   _  __ _  ___   ||
  ||  / _` |/ _` | '__| '_ ` _ \| | '_ \  __) | |_| | | | |/ _` |/ _ \  ||
  || | (_| | (_| | |  | | | | | | | | | |/ __/|  _  | |_| | (_| | (_) | ||
  ||  \__, |\__,_|_|  |_| |_| |_|_|_| |_|_____|_| |_|\__,_|\__, |\___/  ||
  ||  |___/                                                 |___/       ||
  ||                                                                    ||
  ||  -- Main Menu --                                                   ||
  ||                                                                    ||
  ||     [1] Create New Post from Activity                              ||
  ||     [2] Exit                                                       ||
  ||                                                                    ||
  ++--------------------------------------------------------------------++
"""
    print(f"\n{GREEN}{menu_banner}{RESET}")
    return input("  Enter your choice: ").strip()

def create_new_post_flow(api, output_dir, dry_run):
    """Guides user through selecting an activity and creating a post."""
    # 1. Select activity
    activity = display_and_select_activity(api)
    if activity is None:
        print("Returning to main menu.")
        return  # User cancelled or no activities

    # 2. Get post details
    post_name, tags_list = get_post_details()

    # 3. Write the post
    print(f"\nWriting post for '{activity.get('activityName')}'...")
    write_post(activity, post_name, tags_list, output_dir, dry_run)


# ─────────────────────────────────────────────
# ── Main ─────────────────────────────────────
# ─────────────────────────────────────────────


def main():
    load_dotenv()

    # --- Configuration ---
    # Set your default output directory and dry_run status here
    OUTPUT_DIR = Path("~/sprague_runs/content/posts").expanduser()
    DRY_RUN = False  # Set to True to print post content instead of writing file

    # --- Environment Variable Setup ---
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    if not email or not password:
        sys.exit("❌ GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env or environment variables.")

    # --- API Initialization (Run Once) ---
    api = init_api(email, password)
    if not api:
        sys.exit("❌ Failed to initialize API. Exiting.")

    # --- Main Application Loop ---
    while True:
        choice = print_main_menu()

        if choice == '1':
            create_new_post_flow(api, OUTPUT_DIR, DRY_RUN)
        elif choice == '2':
            print("\n👋 Goodbye!")
            break
        else:
            print(f"\n❌ Invalid choice '{choice}'. Please select '1' or '2'.")
        
        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()
