#!/usr/bin/env python3
"""
Evidence Fetchers - Main Menu System

This is the main entry point for the Evidence Fetchers system.
It provides a simple menu to access all functionality.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header():
    """Print the main header."""
    print("=" * 60)
    print("EVIDENCE FETCHERS - MAIN MENU")
    print("=" * 60)
    print()


def print_menu():
    """Print the main menu options."""
    print("Available Options:")
    print()
    print("0) Prerequisites")
    print("   - Do intake in Paramify")
    print("   - Create evidence API key in Paramify")
    print()
    print("1) Select Fetchers")
    print("   - Choose which evidence fetcher scripts to use")
    print("   - Generate evidence_sets.json")
    print()
    print("2) Create Evidence Sets in Paramify")
    print("   - Upload evidence sets to Paramify via API")
    print("   - Option to upload fetcher scripts as artifacts")
    print()
    print("3) Run Fetchers")
    print("   - Execute evidence fetcher scripts")
    print("   - Store evidence in timestamped directories")
    print("   - Option to upload evidence files to Paramify")
    print()
    print("4) Tests")
    print("   - Run validation and test scripts")
    print()
    print("5) Add New Fetcher Script")
    print("   - Add a new fetcher to the library")
    print("   - Includes GitHub contribution instructions")
    print()
    print("6) Evidence Requirement Mapping")
    print("   - Map evidence to requirements from Paramify YAML")
    print("   - Add requirement mappings to evidence sets")
    print()
    print("q) Quit")
    print()


def run_script(script_path: str, *args):
    """Run a script with the given arguments."""
    try:
        cmd = [sys.executable, script_path] + list(args)
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running script: {e}")
        return False
    except FileNotFoundError:
        print(f"Script not found: {script_path}")
        return False


def run_bash_script(script_path: str, *args):
    """Run a bash script with the given arguments."""
    try:
        cmd = ["bash", script_path] + list(args)
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running script: {e}")
        return False
    except FileNotFoundError:
        print(f"Script not found: {script_path}")
        return False


def main():
    """Main menu loop."""
    while True:
        print_header()
        print_menu()
        
        choice = input("Enter your choice (0-6, q to quit): ").strip().lower()
        print()
        
        if choice == 'q':
            print("Goodbye!")
            break
        
        elif choice == '0':
            print("Running Prerequisites...")
            print("=" * 40)
            if os.path.exists("0-prerequisites/prerequisites.py"):
                run_script("0-prerequisites/prerequisites.py")
            else:
                print("Prerequisites script not found. Please check the 0-prerequisites/ folder.")
        
        elif choice == '1':
            print("Running Select Fetchers...")
            print("=" * 40)
            if os.path.exists("1-select-fetchers/select_fetchers.py"):
                run_script("1-select-fetchers/select_fetchers.py")
            else:
                print("Select fetchers script not found. Please check the 1-select-fetchers/ folder.")
        
        elif choice == '2':
            print("Running Create Evidence Sets in Paramify...")
            print("=" * 40)
            if os.path.exists("2-create-evidence-sets/create_evidence_sets.py"):
                run_script("2-create-evidence-sets/create_evidence_sets.py")
            else:
                print("Create evidence sets script not found. Please check the 2-create-evidence-sets/ folder.")
        
        elif choice == '3':
            print("Running Fetchers...")
            print("=" * 40)
            if os.path.exists("3-run-fetchers/run_fetchers.py"):
                run_script("3-run-fetchers/run_fetchers.py")
            else:
                print("Run fetchers script not found. Please check the 3-run-fetchers/ folder.")
        
        elif choice == '4':
            print("Running Tests...")
            print("=" * 40)
            if os.path.exists("4-tests/run_tests.py"):
                run_script("4-tests/run_tests.py")
            else:
                print("Tests script not found. Please check the 4-tests/ folder.")
        
        elif choice == '5':
            print("Running Add New Fetcher Script...")
            print("=" * 40)
            if os.path.exists("5-add-new-fetcher/add_new_fetcher.py"):
                run_script("5-add-new-fetcher/add_new_fetcher.py")
            else:
                print("Add new fetcher script not found. Please check the 5-add-new-fetcher/ folder.")
        
        elif choice == '6':
            print("Running Evidence Requirement Mapping...")
            print("=" * 40)
            if os.path.exists("6-evidence-requirement-mapping/map_requirements.py"):
                run_script("6-evidence-requirement-mapping/map_requirements.py")
            else:
                print("Evidence requirement mapping script not found. Please check the 6-evidence-requirement-mapping/ folder.")
        
        else:
            print("Invalid choice. Please enter 0-6 or q to quit.")
        
        print()
        input("Press Enter to continue...")
        print()


if __name__ == "__main__":
    main()
