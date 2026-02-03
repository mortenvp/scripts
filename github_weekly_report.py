#!/usr/bin/env python3
"""
GitHub Weekly Activity Report

Fetches pull requests and issues where the authenticated user is an author
or contributor for a specified week using the GitHub CLI (gh command).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a weekly report of your GitHub activity (PRs and issues)"
    )
    parser.add_argument(
        "--week",
        type=int,
        help="Week number (1-53). Requires --year.",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Year (e.g., 2026). Requires --week.",
    )
    return parser.parse_args()


def get_week_range(week_num: int = None, year: int = None) -> tuple:
    """
    Calculate the start and end dates for a week.

    Args:
        week_num: Optional week number (1-53).
        year: Optional year (used with week_num).
        If both are None, uses last week.

    Returns:
        Tuple of (start_date, end_date, week_description)
    """
    if week_num is not None and year is not None:
        # Calculate the Monday of the specified week number
        # Week 1 is the first week with a Thursday in the year (ISO 8601)
        jan_4 = datetime(year, 1, 4)
        # Find the Monday of week 1
        week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
        # Calculate the Monday of the requested week
        start_date = week_1_monday + timedelta(weeks=week_num - 1)
    else:
        # Default to last week (Monday to Sunday)
        today = datetime.now(timezone.utc).date()
        # Find this week's Monday
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        # Go back one week to get last Monday
        start_date = datetime.combine(this_monday - timedelta(days=7), datetime.min.time())

    # Week runs Monday to Sunday
    end_date = start_date + timedelta(days=7)
    
    week_description = f"{start_date.strftime('%Y %b %d')} to {(end_date - timedelta(days=1)).strftime('%Y %b %d')}"
    
    return start_date, end_date, week_description


def check_gh_installed() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_current_user() -> str:
    """Get the authenticated GitHub user's login."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error fetching current user: {e.stderr}")
        sys.exit(1)


def search_user_activity(
    username: str, start_date: datetime, end_date: datetime, item_type: str
) -> List[Dict[str, Any]]:
    """
    Search for user's PRs or issues using GitHub search API.

    Args:
        username: GitHub username
        start_date: Start of date range
        end_date: End of date range
        item_type: Either 'pr' or 'issue'

    Returns:
        List of PRs or issues that were updated (created or closed) in the date range
    """
    try:
        # Use gh search to find items by author
        cmd = [
            "gh",
            "search",
            item_type + "s",
            "--author",
            username,
            "--limit",
            "100",
            "--json",
            "number,title,url,repository,state,createdAt,closedAt",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        items = json.loads(result.stdout)
        
        # Filter items that were created or closed in the specified week
        filtered_items = []
        for item in items:
            include_item = False
            
            # Check if created in the week
            if item.get("createdAt"):
                created_at = datetime.strptime(item["createdAt"], "%Y-%m-%dT%H:%M:%SZ")
                if start_date <= created_at < end_date:
                    include_item = True
            
            # Check if closed in the week (gh search returns 0001-01-01 for null)
            if item.get("closedAt") and not item["closedAt"].startswith("0001-01-01"):
                closed_at = datetime.strptime(item["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                if start_date <= closed_at < end_date:
                    include_item = True
            
            if include_item:
                # Add item type to each item
                item["item_type"] = item_type
                filtered_items.append(item)
        
        return filtered_items

    except subprocess.CalledProcessError as e:
        print(f"Error searching {item_type}s: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing {item_type} data: {e}")
        return []


def generate_report(username: str, week_num: int = None, year: int = None) -> None:
    """
    Generate and print a weekly activity report.

    Args:
        username: GitHub username
        week_num: Optional week number
        year: Optional year
    """
    start_date, end_date, week_description = get_week_range(week_num, year)

    print(f"\n{'=' * 70}")
    print(f"GitHub Weekly Activity Report - {username}")
    print(f"Week: {week_description}")
    print(f"{'=' * 70}\n")

    print("Fetching your activity...\n")

    # Fetch pull requests (filtered by created or closed date)
    prs = search_user_activity(username, start_date, end_date, "pr")

    # Fetch issues (filtered by created or closed date)
    issues = search_user_activity(username, start_date, end_date, "issue")

    # Combine all items into a single list
    all_items = prs + issues

    # Print summary
    print(f"{'─' * 70}")
    print("SUMMARY")
    print(f"{'─' * 70}")
    print(f"Total Pull Requests: {len(prs)}")
    print(f"Total Issues: {len(issues)}")
    print(f"Total Items: {len(all_items)}\n")

    if not all_items:
        print("No activity found for this week.")
    else:
        # Sort by repository first, then by creation date within each repo
        sorted_items = sorted(all_items, key=lambda x: (x["repository"]["nameWithOwner"], -datetime.strptime(x["createdAt"], "%Y-%m-%dT%H:%M:%SZ").timestamp()))

        print(f"\n{'=' * 70}")
        print("ACTIVITY")
        print(f"{'=' * 70}\n")

        current_repo = None
        for item in sorted_items:
            created_date = datetime.strptime(
                item["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
            )
            state = item["state"].upper()
            repo_name = item["repository"]["nameWithOwner"]
            item_type = "PR" if item["item_type"] == "pr" else "Issue"

            # Print repository header when it changes
            if current_repo != repo_name:
                if current_repo is not None:
                    print()  # Add spacing between repos
                print(f"Repository: {repo_name}")
                print(f"{'-' * 70}")
                current_repo = repo_name

            print(f"  • [{item_type}] #{item['number']}: {item['title']}")
            print(f"    Status: {state}")
            print(f"    Created: {created_date.strftime('%Y %b %d')}")
            
            if item.get("closedAt") and not item["closedAt"].startswith("0001-01-01"):
                closed_date = datetime.strptime(
                    item["closedAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                print(f"    Closed: {closed_date.strftime('%Y %b %d')}")
            
            print(f"    Link: {item['url']}")
            print()

    print(f"\n{'=' * 70}")
    print("Report generation complete!")
    print(f"{'=' * 70}\n")


def main():
    """Main entry point."""
    args = parse_arguments()

    # Validate arguments
    if (args.week is not None and args.year is None) or (args.year is not None and args.week is None):
        print("Error: --week and --year must be used together")
        sys.exit(1)

    # Check if gh CLI is installed and authenticated
    if not check_gh_installed():
        print("Error: GitHub CLI (gh) is not installed or not authenticated.")
        print("\nTo install gh CLI, visit: https://cli.github.com/")
        print("After installation, run: gh auth login")
        sys.exit(1)

    # Get current user
    username = get_current_user()

    generate_report(username, args.week, args.year)


if __name__ == "__main__":
    main()
