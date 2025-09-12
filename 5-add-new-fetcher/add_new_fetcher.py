#!/usr/bin/env python3
"""
Add New Fetcher Script

This script helps developers add new evidence fetcher scripts to the library
and provides GitHub contribution instructions.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header():
    """Print the add new fetcher header."""
    print("=" * 60)
    print("ADD NEW FETCHER SCRIPT")
    print("=" * 60)
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


def main():
    """Main add new fetcher function."""
    print_header()
    
    print("This script will help you add a new evidence fetcher script to the library.")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("add_evidence_fetcher.py"):
        print("Error: add_evidence_fetcher.py not found.")
        print("Please run this from the 5-add-new-fetcher/ directory.")
        return
    
    print("Available options:")
    print("1) Interactive mode (recommended for new users)")
    print("2) Command line mode (for advanced users)")
    print("3) Validate existing catalog")
    print("4) Show GitHub contribution instructions")
    print()
    
    choice = input("Enter your choice (1-4): ").strip()
    
    if choice == '1':
        print("\nRunning interactive mode...")
        print("This will guide you through adding a new fetcher script.")
        print()
        run_script("add_evidence_fetcher.py", "--interactive")
    
    elif choice == '2':
        print("\nCommand line mode:")
        print("Usage: python add_evidence_fetcher.py --script-file <path> --category <category> --name <name>")
        print()
        print("Example:")
        print("python add_evidence_fetcher.py --script-file ../fetchers/aws/my_new_script.sh --category aws --name 'My New Script'")
        print()
        
        script_file = input("Enter script file path: ").strip()
        category = input("Enter category (aws/k8s/knowbe4/okta): ").strip()
        name = input("Enter script name: ").strip()
        
        if script_file and category and name:
            run_script("add_evidence_fetcher.py", "--script-file", script_file, "--category", category, "--name", name)
        else:
            print("Invalid input. Please provide all required parameters.")
    
    elif choice == '3':
        print("\nValidating catalog...")
        run_script("validate_catalog.py")
    
    elif choice == '4':
        print("\n" + "=" * 60)
        print("GITHUB CONTRIBUTION INSTRUCTIONS")
        print("=" * 60)
        print()
        print("1. Fork the repository on GitHub")
        print("2. Create a new branch for your changes:")
        print("   git checkout -b feature/add-new-fetcher")
        print()
        print("3. Add your new fetcher script to the appropriate directory:")
        print("   - AWS scripts: fetchers/aws/")
        print("   - Kubernetes scripts: fetchers/k8s/")
        print("   - KnowBe4 scripts: fetchers/knowbe4/")
        print("   - Okta scripts: fetchers/okta/")
        print()
        print("4. Use the add_evidence_fetcher.py script to add it to the catalog:")
        print("   python add_evidence_fetcher.py --interactive")
        print()
        print("5. Test your changes:")
        print("   python validate_catalog.py")
        print("   python ../4-tests/run_tests.py")
        print()
        print("6. Commit your changes:")
        print("   git add .")
        print("   git commit -m 'Add new fetcher: [script-name]'")
        print()
        print("7. Push your branch:")
        print("   git push origin feature/add-new-fetcher")
        print()
        print("8. Create a Pull Request on GitHub with:")
        print("   - Description of the new fetcher")
        print("   - What evidence it collects")
        print("   - Any dependencies or requirements")
        print("   - Test results")
        print()
        print("9. Wait for review and merge")
        print()
        print("=" * 60)
    
    else:
        print("Invalid choice. Please enter 1-4.")
        return
    
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print()
    print("After adding your new fetcher script:")
    print("1. Test it thoroughly with sample data")
    print("2. Run validation: python validate_catalog.py")
    print("3. Test the full system: python ../4-tests/run_tests.py")
    print("4. Update documentation if needed")
    print("5. Create a GitHub Pull Request")
    print()
    print("For detailed instructions, see DEVELOPER_GUIDE.md")


if __name__ == "__main__":
    main()
