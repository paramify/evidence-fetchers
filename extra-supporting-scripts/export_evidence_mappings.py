#!/usr/bin/env python3
"""
Export Evidence Mappings from Paramify

This script queries Paramify's REST API to extract evidence UUIDs linked to each KSI indicator
and exports them in JSON and CSV formats.
"""

import argparse
import json
import os
import requests
import sys
import csv
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

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


class ParamifyEvidenceExporter:
    def __init__(self, api_token: str, base_url: str = None):
        self.api_token = api_token
        self.base_url = base_url or os.environ.get("PARAMIFY_API_BASE_URL", "https://app.paramify.com/api/v0")
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def get_all_evidence(self) -> List[Dict]:
        """Get all evidence from Paramify"""
        try:
            response = requests.get(f"{self.base_url}/evidence", headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("evidences", [])
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve evidence: {e}")
            return []
    
    def get_control_implementation(self, program_id: str, control_id: str) -> Optional[Dict]:
        """Get control implementation details"""
        # Try different possible endpoints
        endpoints_to_try = [
            f"{self.base_url}/projects/{program_id}/controls/{control_id}",
            f"{self.base_url}/programs/{program_id}/controls/{control_id}",
            f"{self.base_url}/projects/{program_id}/control-implementations/{control_id}",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(endpoint, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
            except requests.exceptions.RequestException:
                continue
        return None
    
    def get_control_requirement(self, program_id: str, control_id: str) -> Optional[Dict]:
        """Get control requirement details"""
        endpoints_to_try = [
            f"{self.base_url}/projects/{program_id}/controls/{control_id}/requirement",
            f"{self.base_url}/programs/{program_id}/controls/{control_id}/requirement",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(endpoint, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
            except requests.exceptions.RequestException:
                continue
        return None
    
    def extract_evidence_from_control(self, control_data: Dict) -> List[str]:
        """Extract evidence UUIDs from control data"""
        evidence_uuids = []
        
        # Try different possible structures
        if isinstance(control_data, dict):
            # Check for evidence field
            if "evidence" in control_data:
                evidence_list = control_data["evidence"]
                if isinstance(evidence_list, list):
                    for ev in evidence_list:
                        if isinstance(ev, dict) and "id" in ev:
                            evidence_uuids.append(ev["id"])
                        elif isinstance(ev, str):
                            evidence_uuids.append(ev)
            
            # Check for evidences field
            if "evidences" in control_data:
                evidence_list = control_data["evidences"]
                if isinstance(evidence_list, list):
                    for ev in evidence_list:
                        if isinstance(ev, dict) and "id" in ev:
                            evidence_uuids.append(ev["id"])
                        elif isinstance(ev, str):
                            evidence_uuids.append(ev)
            
            # Check for evidenceIds field
            if "evidenceIds" in control_data:
                evidence_list = control_data["evidenceIds"]
                if isinstance(evidence_list, list):
                    evidence_uuids.extend([str(e) for e in evidence_list if e])
            
            # Check nested structures
            if "implementation" in control_data:
                impl = control_data["implementation"]
                if isinstance(impl, dict):
                    evidence_uuids.extend(self.extract_evidence_from_control(impl))
            
            if "validations" in control_data:
                validations = control_data["validations"]
                if isinstance(validations, list):
                    for validation in validations:
                        if isinstance(validation, dict):
                            evidence_uuids.extend(self.extract_evidence_from_control(validation))
        
        return list(set(evidence_uuids))  # Remove duplicates
    
    def export_evidence_mappings(self, program_id: str, output_dir: str):
        """Export evidence mappings for all controls in a program"""
        print(f"Exporting evidence mappings for program: {program_id}")
        
        # Get all control implementations
        print("Fetching control implementations...")
        controls = []
        endpoints_to_try = [
            f"{self.base_url}/projects/{program_id}/controls",
            f"{self.base_url}/programs/{program_id}/controls",
            f"{self.base_url}/projects/{program_id}/control-implementations",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(endpoint, headers=self.headers)
                if response.status_code == 200:
                    controls_data = response.json()
                    # Try different possible response structures
                    controls = (controls_data.get("controlImplementations") or 
                              controls_data.get("controls") or
                              controls_data.get("data") or [])
                    if controls:
                        break
            except requests.exceptions.RequestException:
                continue
        
        if not controls:
            print("Could not fetch controls via REST API, using known control IDs from MCP...")
        
        # If we don't have controls from REST API, use the known control IDs
        if not controls:
            # These are the control IDs we got from MCP
            known_controls = [
                {"id": "db45dfe5-fff9-4962-bd5b-743266b11a00", "labelId": "CED-01"},
                {"id": "71dde061-a360-40d8-acc8-eab07827b0ff", "labelId": "CED-02"},
                {"id": "2e9e75b2-1636-424a-9e59-09a119b09b8d", "labelId": "CED-03"},
                {"id": "0a628c06-b497-4661-b4e7-b12dbaa01557", "labelId": "CMT-01"},
                {"id": "7a76681e-483c-4f99-b833-a53275ad247a", "labelId": "CMT-02"},
                {"id": "3f21ef38-b42f-47e3-a720-f434e95ce4b9", "labelId": "CMT-03"},
                {"id": "80043339-07fd-4f10-b407-823ad9250d62", "labelId": "CMT-04"},
                {"id": "7352ae37-bcab-4428-89b0-51cff74bc1bc", "labelId": "CMT-05"},
                {"id": "5add1654-47eb-403a-b996-f20aa5dec006", "labelId": "CNA-01"},
                {"id": "af204c9d-82c8-4ad5-8500-8c17c529186e", "labelId": "CNA-02"},
                {"id": "cb8bcd32-1af4-4eea-a270-fb7031b6fdaf", "labelId": "CNA-03"},
                {"id": "2f311fbc-40db-4da9-b214-ed65cf51c592", "labelId": "CNA-04"},
                {"id": "9a1cc1a1-c118-4f82-aff6-0d430f597d1f", "labelId": "CNA-05"},
                {"id": "c18f1f4d-9dcf-4b5c-a452-48d51aa95536", "labelId": "CNA-06"},
                {"id": "607906be-5bf8-4dd4-89c6-42b5912910f6", "labelId": "CNA-07"},
                {"id": "fc6e74e5-7425-422c-acf0-60cce0bcd23b", "labelId": "CNA-08"},
                {"id": "33615afb-c4e0-43cc-b607-53fcb9a9efa2", "labelId": "IAM-01"},
                {"id": "44836e19-ef89-4d77-8705-0eaccb33c24b", "labelId": "IAM-02"},
                {"id": "3376922c-3df8-4074-aa55-e8143bbf0528", "labelId": "IAM-03"},
                {"id": "b3d3065f-b59a-4315-8541-0260c1daf90d", "labelId": "IAM-04"},
                {"id": "2e11f04c-fccc-4043-bacb-e1910f87df6a", "labelId": "IAM-05"},
                {"id": "89665151-c3b7-4f49-9b3f-f11fdf3ac104", "labelId": "IAM-06"},
                {"id": "d64f4f12-480e-4b66-b62a-c2440a7121df", "labelId": "IAM-07"},
                {"id": "e0494cbd-e516-488a-a3d6-2453f14aed11", "labelId": "INR-01"},
                {"id": "470fb3ec-d317-4a76-a410-6fac066f2e6e", "labelId": "INR-02"},
                {"id": "0308bdde-b802-4f43-b306-f50abf9a717e", "labelId": "INR-03"},
                {"id": "ef3f09bf-cbe4-406f-a1a8-3d5f3f185d42", "labelId": "MLA-01"},
                {"id": "005c8fc8-9387-473d-8050-e893692d3620", "labelId": "MLA-02"},
                {"id": "e491e757-f7e8-4f20-84de-b6a2beb84af3", "labelId": "MLA-03"},
                {"id": "2bc4b627-8535-4cec-8573-2c21e5bfc4d8", "labelId": "MLA-05"},
                {"id": "cd08fb98-cc5d-4e75-9bbe-14ae7bc3f9fd", "labelId": "MLA-07"},
                {"id": "b02ac62b-bc9b-4865-9608-f865c0b617", "labelId": "MLA-08"},
                {"id": "600d9449-6814-4ef3-aceb-dd11acd2856d", "labelId": "PIY-01"},
                {"id": "d82086bb-f790-4f72-be6a-8c66652918f5", "labelId": "PIY-02"},
                {"id": "b1f3bdf7-ce60-47a4-be9f-6df912a8f3f4", "labelId": "PIY-03"},
                {"id": "702d4d9e-160b-40b6-8227-61586394d2a5", "labelId": "PIY-04"},
                {"id": "571c3da7-ddcb-4083-86e2-c4180eed4552", "labelId": "PIY-05"},
                {"id": "72978aa1-d218-4bf3-b639-a46793f3b13f", "labelId": "PIY-06"},
                {"id": "1810ac31-912b-4561-939d-f65fd7457668", "labelId": "PIY-07"},
                {"id": "6c759672-36d3-4ec1-b26d-d7b7d9b6cde1", "labelId": "RPL-01"},
                {"id": "8525143e-fd37-4785-b264-f859c2c655f3", "labelId": "RPL-02"},
                {"id": "df3d50c0-90cb-43ed-ba05-93cc176cb941", "labelId": "RPL-03"},
                {"id": "e93f8bfb-0e6f-4951-816b-5cf77409a126", "labelId": "RPL-04"},
                {"id": "d8027a25-ac70-4ac4-8c77-2bef9d600998", "labelId": "SVC-01"},
                {"id": "cab69db5-8ee7-42e4-95f1-b940414528f7", "labelId": "SVC-02"},
                {"id": "48d97a52-b80f-4457-bd0a-6bc39ab00370", "labelId": "SVC-03"},
                {"id": "ef0ac078-6f47-47b9-adde-42335b052573", "labelId": "SVC-04"},
                {"id": "ea935232-49cc-476a-bc0f-8cc9f3a5ca14", "labelId": "SVC-05"},
                {"id": "c3419ad3-3fd0-4471-ac02-b2adb0fd458a", "labelId": "SVC-06"},
                {"id": "121aac7f-bc7a-4eff-969f-5ad18f7992b7", "labelId": "SVC-07"},
                {"id": "8176fc11-4688-4afe-ad17-fc43ee03d0fa", "labelId": "SVC-08"},
                {"id": "11c0df9f-4892-471f-9ddc-ffff49a1b891", "labelId": "SVC-09"},
                {"id": "edb85012-298c-40d6-9d86-16415563730d", "labelId": "SVC-10"},
                {"id": "e82f95fe-5e87-4e3d-b873-b83b97fe7ecd", "labelId": "TPR-01"},
                {"id": "4d18cb87-9117-45fb-914b-a51c68bd253b", "labelId": "TPR-02"},
                {"id": "9c7d6462-ae9c-4128-8a5a-c9c7c0418451", "labelId": "TPR-03"},
                {"id": "c1377a2e-e76b-42a4-97dd-cdb759709c91", "labelId": "TPR-04"},
            ]
            controls = known_controls
        
        print(f"Found {len(controls)} controls")
        
        # Get all evidence
        print("Fetching all evidence...")
        all_evidence = self.get_all_evidence()
        print(f"Found {len(all_evidence)} evidence items")
        
        # Create evidence lookup by name/referenceId
        evidence_by_name = {}
        evidence_by_ref = {}
        for ev in all_evidence:
            name = ev.get("name", "").lower()
            ref_id = ev.get("referenceId", "")
            ev_id = ev.get("id")
            if name:
                if name not in evidence_by_name:
                    evidence_by_name[name] = []
                evidence_by_name[name].append(ev)
            if ref_id:
                evidence_by_ref[ref_id] = ev
        
        # Map controls to evidence
        ksi_evidence_map = defaultdict(list)
        evidence_details = {}  # Store evidence details for CSV
        
        print("Mapping controls to evidence...")
        for control in controls:
            control_id = control.get("id")
            ksi_id = control.get("labelId")
            
            if not ksi_id:
                continue
            
            print(f"  Processing {ksi_id}...")
            
            # Try to get control implementation details
            control_data = self.get_control_implementation(program_id, control_id)
            if control_data:
                evidence_uuids = self.extract_evidence_from_control(control_data)
                for ev_uuid in evidence_uuids:
                    if ev_uuid not in ksi_evidence_map[ksi_id]:
                        ksi_evidence_map[ksi_id].append(ev_uuid)
                        # Get evidence details
                        ev_detail = next((e for e in all_evidence if e.get("id") == ev_uuid), None)
                        if ev_detail:
                            evidence_details[ev_uuid] = {
                                "name": ev_detail.get("name", ""),
                                "referenceId": ev_detail.get("referenceId", "")
                            }
            
            # Also try control requirement endpoint
            req_data = self.get_control_requirement(program_id, control_id)
            if req_data:
                evidence_uuids = self.extract_evidence_from_control(req_data)
                for ev_uuid in evidence_uuids:
                    if ev_uuid not in ksi_evidence_map[ksi_id]:
                        ksi_evidence_map[ksi_id].append(ev_uuid)
                        ev_detail = next((e for e in all_evidence if e.get("id") == ev_uuid), None)
                        if ev_detail:
                            evidence_details[ev_uuid] = {
                                "name": ev_detail.get("name", ""),
                                "referenceId": ev_detail.get("referenceId", "")
                            }
        
        # Convert to final format
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        
        # JSON output
        json_output = {}
        for ksi_id, evidence_uuids in sorted(ksi_evidence_map.items()):
            json_output[ksi_id] = evidence_uuids
        
        json_path = output_dir_path / "evidence_mappings.json"
        with open(json_path, 'w') as f:
            json.dump(json_output, f, indent=2)
        print(f"\nJSON export saved to: {json_path}")
        
        # CSV output
        csv_path = output_dir_path / "evidence_mappings.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["KSI_ID", "Evidence_UUID", "Evidence_Name", "Evidence_ReferenceId"])
            
            for ksi_id in sorted(ksi_evidence_map.keys()):
                evidence_uuids = ksi_evidence_map[ksi_id]
                if evidence_uuids:
                    for ev_uuid in evidence_uuids:
                        ev_detail = evidence_details.get(ev_uuid, {})
                        writer.writerow([
                            ksi_id,
                            ev_uuid,
                            ev_detail.get("name", ""),
                            ev_detail.get("referenceId", "")
                        ])
                else:
                    # Write row even if no evidence
                    writer.writerow([ksi_id, "", "", ""])
        
        print(f"CSV export saved to: {csv_path}")
        
        # Print summary
        print(f"\n--- Export Summary ---")
        print(f"Total KSIs: {len(ksi_evidence_map)}")
        ksi_with_evidence = sum(1 for uuids in ksi_evidence_map.values() if uuids)
        print(f"KSIs with evidence: {ksi_with_evidence}")
        print(f"KSIs without evidence: {len(ksi_evidence_map) - ksi_with_evidence}")
        total_evidence_links = sum(len(uuids) for uuids in ksi_evidence_map.values())
        print(f"Total evidence links: {total_evidence_links}")
        
        return json_output


def main():
    load_env_file()
    
    parser = argparse.ArgumentParser(description="Export evidence mappings from Paramify")
    parser.add_argument("--program-id", 
                       default="69a50ce5-ddb7-4472-863c-2f42c88d37fa",
                       help="Paramify program ID")
    parser.add_argument("--output-dir",
                       default="/Users/isaacteuscher/fedramp-20x-pilot",
                       help="Output directory for export files")
    parser.add_argument("--api-token", 
                       help="Paramify API token (or set PARAMIFY_UPLOAD_API_TOKEN env var)")
    parser.add_argument("--base-url",
                       default="https://app.paramify.com/api/v0",
                       help="Paramify API base URL")
    
    args = parser.parse_args()
    
    # Get API token
    api_token = args.api_token or os.environ.get("PARAMIFY_UPLOAD_API_TOKEN")
    if not api_token:
        print("Error: Paramify API token required. Set PARAMIFY_UPLOAD_API_TOKEN environment variable or use --api-token")
        sys.exit(1)
    
    # Initialize exporter
    exporter = ParamifyEvidenceExporter(api_token, args.base_url)
    
    # Export mappings
    exporter.export_evidence_mappings(args.program_id, args.output_dir)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

