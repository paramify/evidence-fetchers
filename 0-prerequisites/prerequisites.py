#!/usr/bin/env python3
"""
Prerequisites Setup

This script helps users set up the prerequisites for using the Evidence Fetchers system.
"""

import os
import sys
from pathlib import Path


def print_header():
    """Print the prerequisites header."""
    print("=" * 60)
    print("PREREQUISITES SETUP")
    print("=" * 60)
    print()


def check_env_file():
    """Check if .env file exists and guide user to create it."""
    env_file = Path(".env")
    
    if env_file.exists():
        print("✓ .env file found")
        return True
    else:
        print("✗ .env file not found")
        print()
        print("Please create a .env file with the following variables:")
        print()
        print("# Paramify API Configuration")
        print("PARAMIFY_UPLOAD_API_TOKEN=your_api_token_here")
        print()
        print()
        return False


def check_python_dependencies():
    """Check and install Python package dependencies."""
    print("Checking Python package dependencies...")
    print()
    
    # Check if requirements.txt exists
    if not os.path.exists("requirements.txt"):
        print("✗ requirements.txt not found")
        return False
    
    # Check if pip is available
    try:
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("✗ pip is not available")
            return False
    except:
        print("✗ pip is not available")
        return False
    
    # Check if required packages are installed
    required_packages = ["requests", "boto3"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            print(f"✗ {package} is not installed")
            missing_packages.append(package)
    
    # Install missing packages if any
    if missing_packages:
        print(f"\nInstalling missing Python packages: {', '.join(missing_packages)}")
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Successfully installed Python dependencies")
                return True
            else:
                print(f"✗ Failed to install Python dependencies: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ Error installing Python dependencies: {e}")
            return False
    
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")
    print()
    
    # Check system dependencies
    system_dependencies = [
        ("python3", "Python 3.x"),
        ("aws", "AWS CLI"),
        ("jq", "jq JSON processor"),
        ("curl", "curl HTTP client"),
        ("kubectl", "Kubernetes CLI (if using K8s scripts)")
    ]
    
    all_system_installed = True
    
    for cmd, name in system_dependencies:
        try:
            result = os.system(f"which {cmd} > /dev/null 2>&1")
            if result == 0:
                print(f"✓ {name} is installed")
            else:
                print(f"✗ {name} is not installed")
                all_system_installed = False
        except:
            print(f"✗ {name} is not installed")
            all_system_installed = False
    
    print()
    
    # Check Python package dependencies
    python_deps_ok = check_python_dependencies()
    
    return all_system_installed and python_deps_ok


def print_paramify_setup():
    """Print instructions for Paramify setup."""
    print("=" * 60)
    print("PARAMIFY SETUP INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Log into your Paramify application")
    print("2. Navigate to Settings > API Keys")
    print("3. Create a new API key with the following permissions:")
    print("   - Evidence Sets: Read/Write")
    print("   - Evidence Artifacts: Read/Write")
    print("   - Requirements: Read")
    print("4. Copy the API key and add it to your .env file")
    print("5. Note your Paramify base URL (usually https://app.paramify.com/api/v0)")
    print()


def print_aws_setup():
    """Print instructions for AWS setup."""
    print("=" * 60)
    print("AWS SETUP INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Install AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
    print("2. Configure AWS credentials:")
    print("   aws configure")
    print("3. Or use AWS profiles:")
    print("   aws configure --profile your-profile-name")
    print("4. Test your configuration:")
    print("   aws sts get-caller-identity")
    print()


def print_k8s_setup():
    """Print instructions for Kubernetes setup."""
    print("=" * 60)
    print("KUBERNETES SETUP INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Install kubectl: https://kubernetes.io/docs/tasks/tools/")
    print("2. Configure kubectl for your cluster:")
    print("   aws eks update-kubeconfig --region us-west-2 --name your-cluster-name")
    print("3. Test your configuration:")
    print("   kubectl cluster-info")
    print()


def main():
    """Main prerequisites setup function."""
    print_header()
    
    print("This script will help you set up the prerequisites for using")
    print("the Evidence Fetchers system.")
    print()
    
    # Check .env file
    env_ok = check_env_file()
    print()
    
    # Check dependencies
    deps_ok = check_dependencies()
    print()
    
    if not env_ok or not deps_ok:
        print("=" * 60)
        print("SETUP REQUIRED")
        print("=" * 60)
        print()
        
        if not env_ok:
            print("Please create the .env file as shown above.")
            print()
        
        if not deps_ok:
            print("Please install the missing dependencies.")
            print()
        
        print("After completing the setup, run this script again to verify.")
        print()
        
        # Show setup instructions
        choice = input("Would you like to see detailed setup instructions? (y/n): ").strip().lower()
        if choice == 'y':
            print()
            print_paramify_setup()
            print_aws_setup()
            print_k8s_setup()
    else:
        print("✓ All prerequisites are met!")
        print()
        print("You can now proceed to:")
        print("1) Select Fetchers (option 1)")
        print("2) Create Evidence Sets in Paramify (option 2)")
        print("3) Run Fetchers (option 3)")


if __name__ == "__main__":
    main()
