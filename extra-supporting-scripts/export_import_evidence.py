#!/usr/bin/env python3
"""
Export and Import Evidence Between Paramify Workspaces

This script exports evidence sets and artifacts from one Paramify workspace
and imports them into another workspace. It handles different environments
(stage, prod, demo) and prevents duplicate uploads.

Usage:
    python export_import_evidence.py
"""

import argparse
import json
import os
import sys
import requests
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add the paramify pusher to the path
sys.path.append(str(Path(__file__).parent.parent / "2-create-evidence-sets"))
from paramify_pusher import ParamifyPusher


def get_base_url(environment: str) -> str:
    """Get the base URL for the specified environment."""
    env_map = {
        "stage": "https://stage.paramify.com/api/v0",
        "prod": "https://app.paramify.com/api/v0",
        "demo": "https://demo.paramify.com/api/v0"
    }
    
    env_lower = environment.lower()
    if env_lower not in env_map:
        raise ValueError(f"Invalid environment: {environment}. Must be one of: stage, prod, demo")
    
    return env_map[env_lower]


class EvidenceExporter:
    """Export evidence sets and artifacts from a Paramify workspace."""
    
    def __init__(self, api_token: str, base_url: str):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_workspace_info(self) -> Optional[Dict]:
        """Get workspace/project information."""
        try:
            response = requests.get(f"{self.base_url}/projects", headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            projects = data.get("projects", [])
            
            if projects:
                if len(projects) == 1:
                    return {
                        "name": projects[0].get("name", "Unknown"),
                        "type": projects[0].get("type", "Unknown"),
                        "id": projects[0].get("id", "Unknown")
                    }
                else:
                    return {
                        "count": len(projects),
                        "projects": projects
                    }
            return None
            
        except requests.exceptions.RequestException:
            return None
    
    def get_all_evidence_sets(self) -> List[Dict]:
        """Get all evidence sets from the workspace."""
        try:
            response = requests.get(f"{self.base_url}/evidence", headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            evidences = data.get("evidences", [])
            print(f"✓ Found {len(evidences)} evidence set(s) in export workspace")
            return evidences
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to retrieve evidence sets: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return []
    
    def get_artifacts_for_evidence(self, evidence_id: str) -> List[Dict]:
        """Get all artifacts for a specific evidence set."""
        try:
            response = requests.get(
                f"{self.base_url}/evidence/{evidence_id}/artifacts",
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            artifacts = data.get("artifacts", [])
            return artifacts
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to retrieve artifacts for evidence {evidence_id}: {e}")
            return []
    
    def download_artifact_file(self, artifact: Dict, output_dir: Path) -> Optional[Path]:
        """Download an artifact file to a local directory."""
        # Skip URL artifacts (they don't have files to download)
        if artifact.get("isUrl", False):
            print(f"  ⊘ Skipping URL artifact: {artifact.get('title', 'unnamed')}")
            return None
        
        pathname = artifact.get("pathname")
        if not pathname:
            print(f"  ⊘ No download URL for artifact: {artifact.get('title', 'unnamed')}")
            return None
        
        original_filename = artifact.get("originalFileName") or artifact.get("title", "artifact")
        
        try:
            # Try downloading without auth header first (for presigned S3 URLs)
            # Presigned URLs are already signed and don't need additional auth
            file_response = requests.get(pathname, timeout=30)
            
            # If that fails with 403/401, try with auth header
            if file_response.status_code in [401, 403]:
                file_response = requests.get(pathname, headers={"Authorization": f"Bearer {self.api_token}"}, timeout=30)
            
            file_response.raise_for_status()
            
            # Save to output directory
            output_path = output_dir / original_filename
            with open(output_path, 'wb') as f:
                f.write(file_response.content)
            
            return output_path
            
        except requests.exceptions.RequestException as e:
            # Check if it's an expired URL or access denied
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 400:
                    print(f"  ⚠️  Presigned URL may be expired or invalid: {original_filename}")
                elif e.response.status_code in [403, 401]:
                    print(f"  ⚠️  Access denied for artifact: {original_filename}")
                else:
                    print(f"  ✗ Failed to download artifact {original_filename}: {e}")
            else:
                print(f"  ✗ Failed to download artifact {original_filename}: {e}")
            return None
    
    def export_evidence(self, output_dir: Optional[Path] = None) -> Dict:
        """Export all evidence sets and artifacts from the workspace."""
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="evidence_export_"))
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        artifacts_dir = output_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        print(f"\nExporting evidence to: {output_dir}")
        
        # Get all evidence sets
        evidence_sets = self.get_all_evidence_sets()
        
        if not evidence_sets:
            print("No evidence sets found to export.")
            return {"evidence_sets": [], "export_dir": str(output_dir)}
        
        exported_data = {
            "export_timestamp": datetime.now().isoformat(),
            "evidence_sets": []
        }
        
        total_artifacts = 0
        downloaded_artifacts = 0
        
        for evidence_set in evidence_sets:
            evidence_id = evidence_set.get("id")
            evidence_name = evidence_set.get("name", "unnamed")
            reference_id = evidence_set.get("referenceId", "")
            
            print(f"\nProcessing evidence set: {evidence_name} (Ref: {reference_id})")
            
            # Get artifacts for this evidence set
            artifacts = self.get_artifacts_for_evidence(evidence_id)
            print(f"  Found {len(artifacts)} artifact(s)")
            
            # Create directory for this evidence set's artifacts
            evidence_artifacts_dir = artifacts_dir / evidence_id
            evidence_artifacts_dir.mkdir(exist_ok=True)
            
            exported_artifacts = []
            
            for artifact in artifacts:
                artifact_id = artifact.get("id")
                artifact_title = artifact.get("title", "unnamed")
                original_filename = artifact.get("originalFileName")
                
                total_artifacts += 1
                
                # Download file artifact (skip URL artifacts)
                file_path = None
                if not artifact.get("isUrl", False):
                    print(f"  Downloading artifact: {artifact_title}...", end=" ")
                    file_path = self.download_artifact_file(artifact, evidence_artifacts_dir)
                    if file_path:
                        downloaded_artifacts += 1
                        print("✓")
                    else:
                        print("✗")
                
                # Store artifact metadata
                exported_artifact = {
                    "id": artifact_id,
                    "title": artifact_title,
                    "originalFileName": original_filename,
                    "note": artifact.get("note"),
                    "effectiveDate": artifact.get("effectiveDate"),
                    "isUrl": artifact.get("isUrl", False),
                    "pathname": artifact.get("pathname") if artifact.get("isUrl", False) else None,
                    "filePath": str(file_path.relative_to(output_dir)) if file_path else None
                }
                exported_artifacts.append(exported_artifact)
            
            # Store evidence set data
            exported_evidence = {
                "id": evidence_set.get("id"),
                "referenceId": reference_id,
                "name": evidence_name,
                "description": evidence_set.get("description", ""),
                "instructions": evidence_set.get("instructions", ""),
                "automated": evidence_set.get("automated", True),
                "artifacts": exported_artifacts
            }
            exported_data["evidence_sets"].append(exported_evidence)
        
        # Save export metadata
        metadata_file = output_dir / "export_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(exported_data, f, indent=2)
        
        print(f"\n✓ Export complete:")
        print(f"  Evidence sets: {len(evidence_sets)}")
        print(f"  Total artifacts: {total_artifacts}")
        print(f"  Downloaded files: {downloaded_artifacts}")
        print(f"  Export directory: {output_dir}")
        
        exported_data["export_dir"] = str(output_dir)
        return exported_data


class EvidenceImporter:
    """Import evidence sets and artifacts into a Paramify workspace."""
    
    def __init__(self, api_token: str, base_url: str):
        self.api_token = api_token
        self.base_url = base_url
        self.pusher = ParamifyPusher(api_token, base_url)
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_workspace_info(self) -> Optional[Dict]:
        """Get workspace/project information."""
        try:
            response = requests.get(f"{self.base_url}/projects", headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            projects = data.get("projects", [])
            
            if projects:
                if len(projects) == 1:
                    return {
                        "name": projects[0].get("name", "Unknown"),
                        "type": projects[0].get("type", "Unknown"),
                        "id": projects[0].get("id", "Unknown")
                    }
                else:
                    return {
                        "count": len(projects),
                        "projects": projects
                    }
            return None
            
        except requests.exceptions.RequestException:
            return None
    
    def check_evidence_set_exists(self, reference_id: str) -> Optional[str]:
        """Check if an evidence set with the given reference ID already exists."""
        return self.pusher.find_existing_evidence_set(reference_id)
    
    def check_artifact_exists(self, evidence_id: str, original_filename: str) -> bool:
        """Check if an artifact with the given filename already exists in the evidence set."""
        try:
            response = requests.get(
                f"{self.base_url}/evidence/{evidence_id}/artifacts",
                headers=self.pusher.headers,
                params={"originalFileName": [original_filename]}
            )
            
            if response.status_code == 200:
                data = response.json()
                artifacts = data.get("artifacts", []) if isinstance(data, dict) else data
                
                # Check if any artifact has the same filename
                for artifact in artifacts:
                    if artifact.get("originalFileName") == original_filename:
                        return True
            
            return False
            
        except requests.exceptions.RequestException:
            return False
    
    def create_evidence_set(self, evidence_data: Dict) -> Tuple[Optional[str], bool]:
        """Create an evidence set in the workspace.
        
        Returns:
            tuple: (evidence_id, was_created) where was_created is True if newly created, False if already existed
        """
        reference_id = evidence_data["referenceId"]
        name = evidence_data["name"]
        description = evidence_data.get("description", "")
        instructions = evidence_data.get("instructions", "")
        automated = evidence_data.get("automated", True)
        
        # Check if already exists
        existing_id = self.check_evidence_set_exists(reference_id)
        if existing_id:
            print(f"  ⊘ Evidence set already exists: {name} (ID: {existing_id})")
            return existing_id, False
        
        # Create new evidence set
        evidence_id = self.pusher.create_evidence_set(
            reference_id, name, description, instructions, automated
        )
        
        if evidence_id:
            print(f"  ✓ Created evidence set: {name} (ID: {evidence_id})")
            return evidence_id, True
        else:
            print(f"  ✗ Failed to create evidence set: {name}")
            return None, False
    
    def upload_artifact(self, evidence_id: str, artifact_data: Dict, export_dir: Path) -> bool:
        """Upload an artifact to an evidence set."""
        artifact_title = artifact_data.get("title", "unnamed")
        original_filename = artifact_data.get("originalFileName")
        is_url = artifact_data.get("isUrl", False)
        
        # Check if artifact already exists
        if original_filename and not is_url:
            if self.check_artifact_exists(evidence_id, original_filename):
                print(f"    ⊘ Artifact already exists: {original_filename} (skipping)")
                return True
        
        # Handle URL artifacts
        if is_url:
            pathname = artifact_data.get("pathname")
            if not pathname:
                print(f"    ✗ URL artifact missing pathname: {artifact_title}")
                return False
            
            # Create URL artifact
            try:
                url_data = {
                    "title": artifact_title,
                    "url": pathname,
                    "note": artifact_data.get("note"),
                    "effectiveDate": artifact_data.get("effectiveDate")
                }
                
                response = requests.post(
                    f"{self.base_url}/evidence/{evidence_id}/artifacts/url",
                    headers=self.pusher.headers,
                    json=url_data
                )
                
                if response.status_code in [200, 201]:
                    print(f"    ✓ Uploaded URL artifact: {artifact_title}")
                    return True
                else:
                    print(f"    ✗ Failed to upload URL artifact (HTTP {response.status_code}): {response.text}")
                    return False
                    
            except requests.exceptions.RequestException as e:
                print(f"    ✗ Error uploading URL artifact: {e}")
                return False
        
        # Handle file artifacts
        file_path = artifact_data.get("filePath")
        if not file_path:
            print(f"    ⊘ Skipping file artifact (download failed during export): {artifact_title}")
            return False  # Return False to count as failed, but don't treat as error
        
        full_file_path = export_dir / file_path
        if not full_file_path.exists():
            print(f"    ⊘ Skipping file artifact (file not found): {artifact_title}")
            return False  # Return False to count as failed, but don't treat as error
        
        # Upload file artifact using pusher
        success = self.pusher.upload_evidence_file(evidence_id, str(full_file_path), artifact_title)
        
        if success:
            print(f"    ✓ Uploaded file artifact: {original_filename}")
        else:
            print(f"    ✗ Failed to upload file artifact: {original_filename}")
        
        return success
    
    def import_evidence(self, export_data: Dict) -> Tuple[int, int, int]:
        """Import evidence sets and artifacts from exported data."""
        export_dir = Path(export_data["export_dir"])
        evidence_sets = export_data.get("evidence_sets", [])
        
        if not evidence_sets:
            print("No evidence sets to import.")
            return (0, 0, 0)
        
        print(f"\nImporting {len(evidence_sets)} evidence set(s)...")
        
        created_count = 0
        skipped_count = 0
        artifact_success_count = 0
        artifact_failed_count = 0
        
        for evidence_data in evidence_sets:
            evidence_name = evidence_data.get("name", "unnamed")
            reference_id = evidence_data.get("referenceId", "")
            
            print(f"\nProcessing evidence set: {evidence_name} (Ref: {reference_id})")
            
            # Create or get evidence set
            evidence_id, was_created = self.create_evidence_set(evidence_data)
            
            if not evidence_id:
                print(f"  ✗ Failed to create/get evidence set, skipping artifacts")
                skipped_count += 1
                continue
            
            # Track if this was newly created
            if was_created:
                created_count += 1
            else:
                skipped_count += 1
            
            # Upload artifacts
            artifacts = evidence_data.get("artifacts", [])
            print(f"  Uploading {len(artifacts)} artifact(s)...")
            
            for artifact_data in artifacts:
                success = self.upload_artifact(evidence_id, artifact_data, export_dir)
                if success:
                    artifact_success_count += 1
                else:
                    artifact_failed_count += 1
        
        print(f"\n✓ Import complete:")
        print(f"  Evidence sets created: {created_count}")
        print(f"  Evidence sets skipped (already exist): {skipped_count}")
        print(f"  Artifacts uploaded: {artifact_success_count}")
        print(f"  Artifacts failed: {artifact_failed_count}")
        
        return (created_count, artifact_success_count, artifact_failed_count)


def main():
    """Main function to handle export and import."""
    parser = argparse.ArgumentParser(
        description="Export and import evidence between Paramify workspaces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python export_import_evidence.py
  
  # Command line mode
  python export_import_evidence.py \\
    --export-workspace-id <uuid> \\
    --export-env prod \\
    --import-workspace-id <uuid> \\
    --import-env stage \\
    --export-token <token> \\
    --import-token <token>
        """
    )
    
    parser.add_argument(
        "--export-workspace-id",
        help="Workspace ID to export from (optional, will prompt if not provided)"
    )
    parser.add_argument(
        "--export-env",
        choices=["stage", "prod", "demo"],
        help="Export environment: stage, prod, or demo"
    )
    parser.add_argument(
        "--import-workspace-id",
        help="Workspace ID to import into (optional, will prompt if not provided)"
    )
    parser.add_argument(
        "--import-env",
        choices=["stage", "prod", "demo"],
        help="Import environment: stage, prod, or demo"
    )
    parser.add_argument(
        "--export-token",
        help="API token for export workspace (optional, uses PARAMIFY_EXPORT_API_TOKEN env var)"
    )
    parser.add_argument(
        "--import-token",
        help="API token for import workspace (optional, uses PARAMIFY_IMPORT_API_TOKEN env var)"
    )
    parser.add_argument(
        "--export-dir",
        help="Directory to store exported evidence (optional, uses temp directory by default)"
    )
    parser.add_argument(
        "--keep-export",
        action="store_true",
        help="Keep exported files after import (default: delete after import)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get export configuration
    if not args.export_env:
        print("Export Environment:")
        print("  1. stage")
        print("  2. prod")
        print("  3. demo")
        export_choice = input("Select export environment (1-3): ").strip()
        export_env_map = {"1": "stage", "2": "prod", "3": "demo"}
        export_env = export_env_map.get(export_choice, "prod")
    else:
        export_env = args.export_env
    
    export_token = args.export_token or os.environ.get("PARAMIFY_EXPORT_API_TOKEN")
    if not export_token:
        export_token = input("Enter export workspace API token: ").strip()
    
    export_base_url = get_base_url(export_env)
    
    # Get import configuration
    if not args.import_env:
        print("\nImport Environment:")
        print("  1. stage")
        print("  2. prod")
        print("  3. demo")
        import_choice = input("Select import environment (1-3): ").strip()
        import_env_map = {"1": "stage", "2": "prod", "3": "demo"}
        import_env = import_env_map.get(import_choice, "prod")
    else:
        import_env = args.import_env
    
    import_token = args.import_token or os.environ.get("PARAMIFY_IMPORT_API_TOKEN")
    if not import_token:
        import_token = input("Enter import workspace API token: ").strip()
    
    import_base_url = get_base_url(import_env)
    
    # Display configuration and workspace info
    print("\n" + "=" * 60)
    print("EXPORT/IMPORT CONFIGURATION")
    print("=" * 60)
    
    # Get export workspace info
    print(f"\nExport Workspace:")
    print(f"  Environment: {export_env}")
    print(f"  Base URL: {export_base_url}")
    exporter = EvidenceExporter(export_token, export_base_url)
    export_workspace = exporter.get_workspace_info()
    if export_workspace:
        if "name" in export_workspace:
            print(f"  Workspace Name: {export_workspace['name']}")
            print(f"  Workspace Type: {export_workspace['type']}")
            print(f"  Workspace ID: {export_workspace['id']}")
        else:
            print(f"  Found {export_workspace['count']} project(s)")
    else:
        print(f"  ⚠️  Could not retrieve workspace information")
    
    # Get import workspace info
    print(f"\nImport Workspace:")
    print(f"  Environment: {import_env}")
    print(f"  Base URL: {import_base_url}")
    importer = EvidenceImporter(import_token, import_base_url)
    import_workspace = importer.get_workspace_info()
    if import_workspace:
        if "name" in import_workspace:
            print(f"  Workspace Name: {import_workspace['name']}")
            print(f"  Workspace Type: {import_workspace['type']}")
            print(f"  Workspace ID: {import_workspace['id']}")
        else:
            print(f"  Found {import_workspace['count']} project(s)")
    else:
        print(f"  ⚠️  Could not retrieve workspace information")
    
    print("=" * 60)
    print()
    
    # Confirm before proceeding
    confirm = input("Proceed with export/import? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Operation cancelled.")
        return
    
    # Export evidence
    print("\n" + "=" * 60)
    print("EXPORTING EVIDENCE")
    print("=" * 60)
    
    export_dir = Path(args.export_dir) if args.export_dir else None
    export_data = exporter.export_evidence(export_dir)
    
    if not export_data.get("evidence_sets"):
        print("\nNo evidence to import.")
        return
    
    # Import evidence
    print("\n" + "=" * 60)
    print("IMPORTING EVIDENCE")
    print("=" * 60)
    created_count, artifact_success, artifact_failed = importer.import_evidence(export_data)
    
    # Cleanup
    if not args.keep_export and export_dir is None:
        export_dir_path = Path(export_data["export_dir"])
        if export_dir_path.exists() and str(export_dir_path).startswith(tempfile.gettempdir()):
            import shutil
            shutil.rmtree(export_dir_path)
            print(f"\n✓ Cleaned up temporary export directory")
    
    # Final summary
    print("\n" + "=" * 60)
    print("EXPORT/IMPORT SUMMARY")
    print("=" * 60)
    print(f"Evidence sets created: {created_count}")
    print(f"Artifacts uploaded: {artifact_success}")
    print(f"Artifacts failed: {artifact_failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()

