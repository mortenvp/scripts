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
from datetime import datetime, timedelta
from typing import List, Dict, Any


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a weekly report of your GitHub activity (PRs and issues)"
    )
    parser.add_argument(
        "--week",
        help="Week to query (format: YYYY-MM-DD for the Monday of that week). "
        "If not provided, defaults to last week (Monday-Sunday).",
    )
    return parser.parse_args()


def get_week_range(week_str: str = None) -> tuple:
    """
    Calculate the start and end dates for a week.

    Args:
        week_str: Optional date string in format YYYY-MM-DD (should be a Monday).
                 If None, uses last week.

    Returns:
        Tuple of (start_date, end_date, week_description)
    """
    if week_str:
        try:
            # Parse the provided date
            provided_date = datetime.strptime(week_str, "%Y-%m-%d")
            # Find the Monday of that week
            days_since_monday = provided_date.weekday()
            start_date = provided_date - timedelta(days=days_since_monday)
        except ValueError:
            print(f"Error: Invalid date format '{week_str}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        # Default to last week (Monday to Sunday)
        today = datetime.now()
        # Find last Monday
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        start_date = last_monday

    # Week runs Monday to Sunday
    end_date = start_date + timedelta(days=7)
    
    week_description = f"{start_date.strftime('%Y-%m-%d')} to {(end_date - timedelta(days=1)).strftime('%Y-%m-%d')}"
    
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
                filtered_items.append(item)
        
        return filtered_items

    except subprocess.CalledProcessError as e:
        print(f"Error searching {item_type}s: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing {item_type} data: {e}")
        return []


def generate_report(username: str, week_str: str = None) -> None:
    """
    Generate and print a weekly activity report.

    Args:
        username: GitHub username
        week_str: Optional week string in format YYYY-MM-DD
    """
    start_date, end_date, week_description = get_week_range(week_str)

    print(f"\n{'=' * 70}")
    print(f"GitHub Weekly Activity Report - {username}")
    print(f"Week: {week_description}")
    print(f"{'=' * 70}\n")

    print("Fetching your activity...\n")

    # Fetch pull requests (filtered by created or closed date)
    prs = search_user_activity(username, start_date, end_date, "pr")

    # Fetch issues (filtered by created or closed date)
    issues = search_user_activity(username, start_date, end_date, "issue")

    # Print summary
    print(f"{'─' * 70}")
    print("SUMMARY")
    print(f"{'─' * 70}")
    print(f"Total Pull Requests: {len(prs)}")
    print(f"Total Issues: {len(issues)}")
    print(f"Total Items: {len(prs) + len(issues)}\n")

    # Group by repository
    repo_data = {}
    for pr in prs:
        repo_name = pr["repository"]["nameWithOwner"]
        if repo_name not in repo_data:
            repo_data[repo_name] = {"prs": [], "issues": []}
        repo_data[repo_name]["prs"].append(pr)

    for issue in issues:
        repo_name = issue["repository"]["nameWithOwner"]
        if repo_name not in repo_data:
            repo_data[repo_name] = {"prs": [], "issues": []}
        repo_data[repo_name]["issues"].append(issue)

    # Print detailed results per repository
    for repo_name in sorted(repo_data.keys()):
        repo_prs = repo_data[repo_name]["prs"]
        repo_issues = repo_data[repo_name]["issues"]

        print(f"\n{'=' * 70}")
        print(f"Repository: {repo_name}")
        print(f"{'=' * 70}")

        if repo_prs:
            print(f"\n📌 Pull Requests ({len(repo_prs)}):")
            print(f"{'-' * 70}")
            for pr in sorted(repo_prs, key=lambda x: x["createdAt"], reverse=True):
                created_date = datetime.strptime(
                    pr["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                state = pr["state"].upper()
                status = f" [{state}]"

                print(f"  • #{pr['number']}: {pr['title']}{status}")
                print(f"    Created: {created_date.strftime('%Y-%m-%d')}")
                
                if pr.get("closedAt") and not pr["closedAt"].startswith("0001-01-01"):
                    closed_date = datetime.strptime(
                        pr["closedAt"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    print(f"    Closed: {closed_date.strftime('%Y-%m-%d')}")
                
                print(f"    Link: {pr['url']}")
                print()

        if repo_issues:
            print(f"🔧 Issues ({len(repo_issues)}):")
            print(f"{'-' * 70}")
            for issue in sorted(
                repo_issues, key=lambda x: x["createdAt"], reverse=True
            ):
                created_date = datetime.strptime(
                    issue["createdAt"], "%Y-%m-%dT%H:%M:%SZ"
                )
                state = issue["state"].upper()
                status = f" [{state}]"

                print(f"  • #{issue['number']}: {issue['title']}{status}")
                print(f"    Created: {created_date.strftime('%Y-%m-%d')}")
                
                if issue.get("closedAt") and not issue["closedAt"].startswith("0001-01-01"):
                    closed_date = datetime.strptime(
                        issue["closedAt"], "%Y-%m-%dT%H:%M:%SZ"
                    )
                    print(f"    Closed: {closed_date.strftime('%Y-%m-%d')}")
                
                print(f"    Link: {issue['url']}")
                print()

    if not repo_data:
        print("No activity found for this week.")

    print(f"\n{'=' * 70}")
    print("Report generation complete!")
    print(f"{'=' * 70}\n")


def main():
    """Main entry point."""
    args = parse_arguments()

    # Check if gh CLI is installed and authenticated
    if not check_gh_installed():
        print("Error: GitHub CLI (gh) is not installed or not authenticated.")
        print("\nTo install gh CLI, visit: https://cli.github.com/")
        print("After installation, run: gh auth login")
        sys.exit(1)

    # Get current user
    username = get_current_user()

    generate_report(username, args.week)


if __name__ == "__main__":
    main()
