#!/usr/bin/env python3
"""
GitHub Activity Report Generator

Fetches closed pull requests and issues from specified repositories
for a given month using the GitHub CLI (gh command).
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict


# ==================== CONFIGURATION ====================
# Add or remove repositories here (format: "owner/repo")
REPOSITORIES = [
    "steinwurf/plumr",
    "steinwurf/raft",
    "steinwurf/kodo",
    "steinwurf/dummynet",
    "steinwurf/abacus",
    "steinwurf/poke",
    "steinwurf/cmake-toolchains",
    "steinwurf/ouroboros",
    "steinwurf/plumr-release-testing",
    "steinwurf/npdbg",
    "steinwurf/slide",
    "steinwurf/rely",
    "steinwurf/fifi",
    # Add more repositories as needed
]
# =======================================================


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a report of closed PRs and issues from GitHub repositories"
    )
    parser.add_argument("month", help="Month to query (format: YYYY-MM, e.g., 2026-01)")
    return parser.parse_args()


def parse_month(month_str: str) -> tuple:
    """
    Parse month string and return start and end datetime objects.

    Args:
        month_str: Month in format YYYY-MM

    Returns:
        Tuple of (start_date, end_date)
    """
    try:
        year, month = map(int, month_str.split("-"))
        start_date = datetime(year, month, 1)

        # Calculate end date (first day of next month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        return start_date, end_date
    except (ValueError, AttributeError):
        print(f"Error: Invalid month format '{month_str}'. Use YYYY-MM (e.g., 2026-01)")
        sys.exit(1)


def check_gh_installed() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def fetch_closed_prs(
    repo: str, start_date: datetime, end_date: datetime
) -> List[Dict[str, Any]]:
    """
    Fetch closed pull requests for a repository.

    Args:
        repo: Repository in format "owner/repo"
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of closed PRs
    """
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "closed",
        "--limit",
        "1000",
        "--json",
        "number,title,url,closedAt,mergedAt",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        prs = json.loads(result.stdout)

        # Filter PRs closed in the specified month
        filtered_prs = []
        for pr in prs:
            if pr.get("closedAt"):
                closed_at = datetime.strptime(pr["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                if start_date <= closed_at < end_date:
                    filtered_prs.append(pr)

        return filtered_prs

    except subprocess.CalledProcessError as e:
        print(f"Error fetching PRs from {repo}: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing PR data from {repo}: {e}")
        return []


def fetch_closed_issues(
    repo: str, start_date: datetime, end_date: datetime
) -> List[Dict[str, Any]]:
    """
    Fetch closed issues for a repository.

    Args:
        repo: Repository in format "owner/repo"
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of closed issues
    """
    cmd = [
        "gh",
        "issue",
        "list",
        "--repo",
        repo,
        "--state",
        "closed",
        "--limit",
        "1000",
        "--json",
        "number,title,url,closedAt",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        issues = json.loads(result.stdout)

        # Filter issues closed in the specified month
        filtered_issues = []
        for issue in issues:
            if issue.get("closedAt"):
                closed_at = datetime.strptime(issue["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                if start_date <= closed_at < end_date:
                    filtered_issues.append(issue)

        return filtered_issues

    except subprocess.CalledProcessError as e:
        print(f"Error fetching issues from {repo}: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing issue data from {repo}: {e}")
        return []


def generate_report(repos: List[str], month_str: str) -> None:
    """
    Generate and print a report of closed PRs and issues.

    Args:
        repos: List of repositories in format "owner/repo"
        month_str: Month in format YYYY-MM
    """
    start_date, end_date = parse_month(month_str)

    print(f"\n{'='*70}")
    print(f"GitHub Activity Report - {start_date.strftime('%B %Y')}")
    print(f"{'='*70}\n")

    total_prs = 0
    total_issues = 0
    repo_data = defaultdict(lambda: {"prs": [], "issues": []})

    # Fetch data for each repository
    for repo in repos:
        print(f"Fetching data from {repo}...")

        # Fetch pull requests
        prs = fetch_closed_prs(repo, start_date, end_date)
        repo_data[repo]["prs"] = prs
        total_prs += len(prs)

        # Fetch issues
        issues = fetch_closed_issues(repo, start_date, end_date)
        repo_data[repo]["issues"] = issues
        total_issues += len(issues)

    print()

    # Print summary
    print(f"{'─'*70}")
    print(f"SUMMARY")
    print(f"{'─'*70}")
    print(f"Total Repositories: {len(repos)}")
    print(f"Total Closed Pull Requests: {total_prs}")
    print(f"Total Closed Issues: {total_issues}")
    print(f"Total Items: {total_prs + total_issues}\n")

    # Print detailed results per repository
    for repo in repos:
        prs = repo_data[repo]["prs"]
        issues = repo_data[repo]["issues"]

        if not prs and not issues:
            continue

        print(f"\n{'='*70}")
        print(f"Repository: {repo}")
        print(f"{'='*70}")

        if prs:
            print(f"\n📌 Closed Pull Requests ({len(prs)}):")
            print(f"{'-'*70}")
            for pr in prs:
                closed_date = datetime.strptime(pr["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                merged_status = " [MERGED]" if pr.get("mergedAt") else " [CLOSED]"
                print(f"  • #{pr['number']}: {pr['title']}{merged_status}")
                print(f"    Closed: {closed_date.strftime('%Y-%m-%d')}")
                print(f"    Link: {pr['url']}")
                print()

        if issues:
            print(f"🔧 Closed Issues ({len(issues)}):")
            print(f"{'-'*70}")
            for issue in issues:
                closed_date = datetime.strptime(issue["closedAt"], "%Y-%m-%dT%H:%M:%SZ")
                print(f"  • #{issue['number']}: {issue['title']}")
                print(f"    Closed: {closed_date.strftime('%Y-%m-%d')}")
                print(f"    Link: {issue['url']}")
                print()

    print(f"\n{'='*70}")
    print("Report generation complete!")
    print(f"{'='*70}\n")


def main():
    """Main entry point."""
    args = parse_arguments()

    # Check if gh CLI is installed and authenticated
    if not check_gh_installed():
        print("Error: GitHub CLI (gh) is not installed or not authenticated.")
        print("\nTo install gh CLI, visit: https://cli.github.com/")
        print("After installation, run: gh auth login")
        sys.exit(1)

    if not REPOSITORIES:
        print("Error: No repositories configured.")
        print("Please edit the REPOSITORIES list at the top of the script.")
        sys.exit(1)

    generate_report(REPOSITORIES, args.month)


if __name__ == "__main__":
    main()
