#!/usr/bin/env python3
"""
Delete All Evidence from Paramify Workspace

This script uses the Paramify API to delete all evidence in the workspace.

⚠️  WARNING: This operation is irreversible and will permanently delete all evidence
   and artifacts. This script should ONLY be used carefully when you want to completely
   clear out all evidence from your workspace (e.g., starting fresh, testing, or
   cleaning up test data).

The script requires TWO confirmations before proceeding with deletion:
1. First confirmation: Acknowledge understanding of the risks
2. Second confirmation: Type 'DELETE ALL' to proceed with deletion
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Add the paramify pusher to the path to reuse the base URL logic
sys.path.append(str(Path(__file__).parent.parent / "2-create-evidence-sets"))
from paramify_pusher import ParamifyPusher


def print_header():
    """Print the delete header."""
    print("=" * 60)
    print("DELETE ALL EVIDENCE FROM PARAMIFY")
    print("=" * 60)
    print()


def get_projects(api_token: str, base_url: str):
    """Fetch all projects (programs) from Paramify."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{base_url}/projects", headers=headers)
        response.raise_for_status()
        
        data = response.json()
        projects = data.get("projects", [])
        return projects
        
    except requests.exceptions.RequestException as e:
        # Handle permission errors gracefully
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 403:
                print("⚠️  API key does not have permission to access /projects endpoint")
                print("   Continuing without program information...")
            else:
                print(f"✗ Failed to retrieve projects: {e}")
                if hasattr(e.response, 'text'):
                    print(f"Response: {e.response.text}")
        else:
            print(f"✗ Failed to retrieve projects: {e}")
        return []


def get_all_evidence(api_token: str, base_url: str):
    """Fetch all evidence from Paramify workspace."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{base_url}/evidence", headers=headers)
        response.raise_for_status()
        
        data = response.json()
        evidences = data.get("evidences", [])
        return evidences
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to retrieve evidence: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None


def delete_evidence(api_token: str, base_url: str, evidence_id: str, evidence_name: str = None):
    """Delete a single evidence record by ID."""
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.delete(f"{base_url}/evidence/{evidence_id}", headers=headers)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        name_str = f" ({evidence_name})" if evidence_name else ""
        print(f"✗ Failed to delete evidence {evidence_id}{name_str}: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return False


def main():
    """Main delete function."""
    print_header()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API configuration
    api_token = os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    base_url = os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
    
    if not api_token:
        print("✗ PARAMIFY_UPLOAD_API_TOKEN environment variable not set")
        print("\nPlease set PARAMIFY_UPLOAD_API_TOKEN in your .env file")
        return
    
    print(f"Using API base URL: {base_url}")
    print()
    
    # Fetch projects to display workspace/program name
    print("Fetching projects (programs)...")
    projects = get_projects(api_token, base_url)
    
    if projects:
        print(f"\nWorkspace/Program Information:")
        if len(projects) == 1:
            project = projects[0]
            print(f"  Program Name: {project.get('name', 'Unknown')}")
            print(f"  Program Type: {project.get('type', 'Unknown')}")
            print(f"  Program ID: {project.get('id', 'Unknown')}")
        else:
            print(f"  Found {len(projects)} program(s):")
            for idx, project in enumerate(projects, 1):
                print(f"    {idx}. {project.get('name', 'Unknown')} (Type: {project.get('type', 'Unknown')}, ID: {project.get('id', 'Unknown')[:8]}...)")
        print()
    else:
        # projects is an empty list if permission denied or error occurred
        print()
    
    # Fetch all evidence
    print("Fetching all evidence from workspace...")
    evidences = get_all_evidence(api_token, base_url)
    
    if evidences is None:
        print("\nFailed to fetch evidence. Cannot proceed.")
        return
    
    if not evidences:
        print("✓ No evidence found in workspace.")
        return
    
    # Display evidence summary
    workspace_info = ""
    if len(projects) == 1:
        workspace_info = f" in program '{projects[0].get('name', 'Unknown')}'"
    elif len(projects) > 1:
        workspace_info = f" (across {len(projects)} program(s))"
    
    print(f"\nFound {len(evidences)} evidence record(s){workspace_info}:")
    for idx, evidence in enumerate(evidences, 1):
        evidence_id = evidence.get("id", "unknown")
        name = evidence.get("name", "unnamed")
        reference_id = evidence.get("referenceId", "no reference ID")
        print(f"  {idx}. {name} (ID: {evidence_id[:8]}..., Ref: {reference_id})")
    
    # First Warning
    workspace_name = ""
    if len(projects) == 1:
        workspace_name = f" from program '{projects[0].get('name', 'Unknown')}'"
    elif len(projects) > 1:
        workspace_name = f" from {len(projects)} program(s)"
    
    print(f"\n{'='*60}")
    print("⚠️  WARNING #1: DESTRUCTIVE OPERATION")
    print(f"{'='*60}")
    print(f"This operation will PERMANENTLY DELETE ALL EVIDENCE{workspace_name} in your workspace.")
    print("This includes:")
    print("  • All evidence records")
    print("  • All associated artifacts")
    print("  • All associated files and attachments")
    print("  • All evidence history and metadata")
    print()
    print("⚠️  This operation is IRREVERSIBLE - deleted evidence cannot be recovered!")
    print()
    print("⚠️  This script should ONLY be used carefully when you want to completely")
    print("    clear out all evidence from your workspace (e.g., starting fresh,")
    print("    testing, or cleaning up test data).")
    print(f"{'='*60}")
    print()
    
    confirm1 = input("⚠️  Do you understand the risks and want to proceed? (yes/no): ").strip().lower()
    if confirm1 != 'yes':
        print("Delete cancelled.")
        return
    
    print()
    
    # Second Warning
    print(f"{'='*60}")
    print("⚠️  WARNING #2: FINAL CONFIRMATION REQUIRED")
    print(f"{'='*60}")
    print(f"You are about to delete {len(evidences)} evidence record(s){workspace_name} from your workspace.")
    print()
    print("⚠️  This is your LAST chance to cancel this operation.")
    print("⚠️  Once you confirm, ALL evidence will be permanently deleted.")
    print()
    print("⚠️  If you are unsure, type 'CANCEL' to abort.")
    print("⚠️  If you are certain, type 'DELETE ALL' to proceed.")
    print(f"{'='*60}")
    print()
    
    confirm2 = input("Type 'DELETE ALL' to confirm deletion, or 'CANCEL' to abort: ").strip()
    if confirm2 == 'CANCEL' or confirm2 == 'cancel':
        print("Delete cancelled.")
        return
    if confirm2 != 'DELETE ALL':
        print("Invalid confirmation. Delete cancelled.")
        print("(You must type exactly 'DELETE ALL' to proceed)")
        return
    
    print()
    print("Deleting evidence...")
    print()
    
    # Delete each evidence
    deleted_count = 0
    failed_count = 0
    
    for evidence in evidences:
        evidence_id = evidence.get("id")
        evidence_name = evidence.get("name", "unnamed")
        reference_id = evidence.get("referenceId", "no reference ID")
        
        print(f"Deleting: {evidence_name} (Ref: {reference_id})...", end=" ")
        
        if delete_evidence(api_token, base_url, evidence_id, evidence_name):
            print("✓")
            deleted_count += 1
        else:
            print("✗")
            failed_count += 1
    
    # Summary
    print()
    print(f"{'='*60}")
    print("DELETE SUMMARY")
    print(f"{'='*60}")
    print(f"Total evidence: {len(evidences)}")
    print(f"Successfully deleted: {deleted_count}")
    print(f"Failed: {failed_count}")
    
    if failed_count == 0:
        print("\n✓ All evidence deleted successfully!")
    else:
        print(f"\n⚠️  {failed_count} evidence record(s) failed to delete.")


if __name__ == "__main__":
    main()

