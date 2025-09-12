#!/usr/bin/env python3
"""
Paramify Evidence Pusher

Reads summary.json and finds all evidence files from that run
Uploads each file to Paramify via API:
- Sends metadata: check name, resource, timestamp, pass/fail
- Attaches raw JSON evidence file
- Records result in upload_log.json
"""

import argparse
import json
import os
import requests
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path(".env")
    if env_file.exists():
        print(f"Loading environment variables from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    print(f"  Loaded {key}")


class ParamifyPusher:
    def __init__(self, api_token: str, base_url: str = None):
        self.api_token = api_token
        # Use provided base_url, environment variable, or default
        self.base_url = base_url or os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.upload_log = []
    
    def load_evidence_sets(self, evidence_sets_file: str = "evidence_sets.json") -> Dict:
        """Load evidence sets configuration"""
        with open(evidence_sets_file, 'r') as f:
            return json.load(f)
    
    def get_evidence_set_info(self, check_name: str, evidence_sets: Dict) -> Optional[Dict]:
        """Get evidence set information for a check"""
        return evidence_sets.get("evidence_sets", {}).get(check_name)
    
    def find_existing_evidence_object(self, reference_id: str) -> Optional[str]:
        """Find existing Evidence Object by reference ID"""
        print(f"Checking for existing Evidence Object with reference ID: {reference_id}")
        
        try:
            response = requests.get(f"{self.base_url}/evidence", headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            for evidence in data.get("evidences", []):
                if evidence.get("referenceId") == reference_id:
                    evidence_id = evidence.get("id")
                    print(f"Found existing Evidence Object: {evidence_id}")
                    return evidence_id
            
            print(f"No existing Evidence Object found for reference ID: {reference_id}")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve Evidence Objects: {e}")
            return None
    
    def create_evidence_object(self, reference_id: str, name: str, description: str, 
                             instructions: str, automated: bool = True) -> Optional[str]:
        """Create new Evidence Object"""
        print(f"Creating Evidence Object: {name}")
        
        data = {
            "referenceId": reference_id,
            "name": name,
            "description": description,
            "instructions": instructions,
            "automated": automated
        }
        
        try:
            response = requests.post(f"{self.base_url}/evidence", headers=self.headers, json=data)
            
            if response.status_code in [200, 201]:
                result = response.json()
                evidence_id = result.get("id")
                print(f"Evidence Object created successfully: {evidence_id}")
                return evidence_id
            elif response.status_code == 400:
                # Check if it's a "Reference ID already exists" error
                error_data = response.json()
                error_msg = error_data.get("message") or error_data.get("error", "Unknown error")
                if "Reference ID already exists" in error_msg:
                    print("Evidence Object already exists, attempting to find it...")
                    return self.find_existing_evidence_object(reference_id)
                else:
                    print(f"Failed to create Evidence Object (HTTP {response.status_code}): {error_msg}")
                    return None
            else:
                print(f"Failed to create Evidence Object (HTTP {response.status_code})")
                print(response.text)
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error creating evidence object: {e}")
            return None
    
    def get_or_create_evidence_object(self, evidence_set_info: Dict) -> Optional[str]:
        """Get or create Evidence Object for a check"""
        reference_id = evidence_set_info["id"]
        name = evidence_set_info["name"]
        description = evidence_set_info["description"]
        instructions = evidence_set_info["instructions"]
        
        print(f"Processing Evidence Object: {reference_id} - {name}")
        
        # Try to find existing Evidence Object
        evidence_id = self.find_existing_evidence_object(reference_id)
        if evidence_id:
            return evidence_id
        
        # Create new Evidence Object
        return self.create_evidence_object(reference_id, name, description, instructions)
    
    def upload_evidence_file(self, evidence_id: str, evidence_file_path: str, check_name: str) -> bool:
        """Upload evidence file as artifact to Evidence Object"""
        if not Path(evidence_file_path).exists():
            print(f"Evidence file not found: {evidence_file_path}")
            return False
        
        print(f"Uploading artifact: {Path(evidence_file_path).name}")
        
        # Create artifact metadata
        artifact_data = {
            "title": f"{check_name} Results",
            "note": f"Automated evidence collection for {check_name}",
            "effectiveDate": datetime.now().isoformat() + "Z"
        }
        
        try:
            # Create temporary artifact JSON file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_artifact:
                json.dump(artifact_data, temp_artifact)
                temp_artifact_path = temp_artifact.name
            
            # Upload using multipart form data
            with open(evidence_file_path, 'rb') as f, open(temp_artifact_path, 'rb') as artifact_f:
                files = {
                    'file': f,
                    'artifact': ('artifact.json', artifact_f, 'application/json')
                }
                
                headers = {"Authorization": f"Bearer {self.api_token}"}
                
                response = requests.post(
                    f"{self.base_url}/evidence/{evidence_id}/artifacts/upload",
                    headers=headers,
                    files=files
                )
                
                # Clean up temp file
                os.unlink(temp_artifact_path)
                
                if response.status_code in [200, 201]:
                    print(f"✓ Artifact uploaded successfully")
                    return True
                else:
                    print(f"✗ Failed to upload artifact (HTTP {response.status_code})")
                    print(response.text)
                    return False
                    
        except requests.exceptions.RequestException as e:
            print(f"Error uploading evidence file: {e}")
            return False
        except Exception as e:
            print(f"Error in upload process: {e}")
            return False
    
    def process_summary(self, summary_path: str) -> List[Dict]:
        """Process summary.json and upload evidence"""
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        evidence_sets = self.load_evidence_sets()
        results = []
        
        for result in summary["results"]:
            # Handle both "check" and "script" field names
            check_name = result.get("check") or result.get("script")
            resource = result.get("resource", "unknown")
            status = result["status"]
            evidence_file = result["evidence_file"]
            timestamp = summary["timestamp"]
            
            print(f"Processing: {check_name} for {resource} ({status})")
            
            # Skip if no evidence file (failed scripts)
            if not evidence_file:
                print(f"Skipping {check_name} - no evidence file")
                continue
            
            # Get evidence set info
            evidence_set_info = self.get_evidence_set_info(check_name, evidence_sets)
            if not evidence_set_info:
                print(f"Warning: No evidence set info found for {check_name}")
                continue
            
            # Get or create Evidence Object
            evidence_id = self.get_or_create_evidence_object(evidence_set_info)
            if not evidence_id:
                print(f"Failed to get/create Evidence Object for {check_name}")
                continue
            
            # Upload evidence file
            upload_success = self.upload_evidence_file(evidence_id, evidence_file, check_name)
            
            # Record result
            upload_result = {
                "check": check_name,
                "resource": resource,
                "status": status,
                "evidence_file": evidence_file,
                "evidence_object_id": evidence_id,
                "upload_success": upload_success,
                "timestamp": datetime.now().isoformat()
            }
            
            results.append(upload_result)
            
            if upload_success:
                print(f"✓ Successfully uploaded evidence for {check_name}")
            else:
                print(f"✗ Failed to upload evidence for {check_name}")
        
        return results
    
    def save_upload_log(self, results: List[Dict], log_path: str = "upload_log.json"):
        """Save upload results to log file"""
        log_data = {
            "upload_timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"Upload log saved to: {log_path}")


def main():
    # Load environment variables from .env file
    load_env_file()
    
    parser = argparse.ArgumentParser(description="Upload evidence to Paramify")
    parser.add_argument("summary_path", help="Path to summary.json file")
    parser.add_argument("--api-token", help="Paramify API token")
    parser.add_argument("--base-url", default="https://app.paramify.com/api/v0", 
                       help="Paramify API base URL")
    parser.add_argument("--log-file", default="upload_log.json", 
                       help="Upload log file path")
    
    args = parser.parse_args()
    
    # Get API token
    api_token = args.api_token or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    if not api_token:
        print("Error: Paramify API token required. Set PARAMIFY_UPLOAD_API_TOKEN environment variable or use --api-token")
        sys.exit(1)
    
    # Check if summary file exists
    if not Path(args.summary_path).exists():
        print(f"Error: Summary file not found: {args.summary_path}")
        sys.exit(1)
    
    # Initialize pusher
    pusher = ParamifyPusher(api_token, args.base_url)
    
    # Process summary and upload evidence
    print(f"Processing summary: {args.summary_path}")
    results = pusher.process_summary(args.summary_path)
    
    # Save upload log
    pusher.save_upload_log(results, args.log_file)
    
    # Print summary
    success_count = sum(1 for r in results if r["upload_success"])
    total_count = len(results)
    
    print(f"\n--- Upload Summary ---")
    print(f"Total: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    return 0 if success_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
