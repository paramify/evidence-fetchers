#!/usr/bin/env python3
"""
Script to provide a summary of the evidence-KSI mappings.
"""

import json
from collections import defaultdict

def load_evidence_sets(file_path: str) -> dict:
    """Load the evidence sets with requirements."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def analyze_mappings(evidence_sets: dict):
    """Analyze and summarize the evidence-KSI mappings."""
    
    # Count total evidence sets and those with requirements
    total_evidence_sets = len(evidence_sets.get('evidence_sets', {}))
    evidence_with_requirements = 0
    evidence_without_requirements = 0
    
    # Count KSI occurrences
    ksi_counts = defaultdict(int)
    all_ksis = set()
    
    # Evidence sets by KSI category
    ksi_categories = defaultdict(list)
    
    print("=== EVIDENCE-KSI MAPPING ANALYSIS ===\n")
    
    for evidence_key, evidence_data in evidence_sets.get('evidence_sets', {}).items():
        evidence_name = evidence_data.get('name', '')
        requirements = evidence_data.get('requirements', [])
        
        if requirements:
            evidence_with_requirements += 1
            print(f" {evidence_key}: {requirements}")
            
            # Count KSI occurrences
            for ksi in requirements:
                ksi_counts[ksi] += 1
                all_ksis.add(ksi)
                
                # Categorize by KSI prefix
                if ksi.startswith('CNA-'):
                    ksi_categories['Cloud Native Architecture (CNA)'].append(evidence_key)
                elif ksi.startswith('CIA-'):
                    ksi_categories['Confidentiality, Integrity, Availability (CIA)'].append(evidence_key)
                elif ksi.startswith('CSC-'):
                    ksi_categories['Cloud Security Controls (CSC)'].append(evidence_key)
                elif ksi.startswith('SVC-'):
                    ksi_categories['Service Controls (SVC)'].append(evidence_key)
                elif ksi.startswith('IAM-'):
                    ksi_categories['Identity and Access Management (IAM)'].append(evidence_key)
                elif ksi.startswith('CMT-'):
                    ksi_categories['Change Management (CMT)'].append(evidence_key)
                elif ksi.startswith('MLA-'):
                    ksi_categories['Monitoring and Logging (MLA)'].append(evidence_key)
                elif ksi.startswith('PIY-'):
                    ksi_categories['Program Implementation (PIY)'].append(evidence_key)
                elif ksi.startswith('TPR-'):
                    ksi_categories['Third Party Risk (TPR)'].append(evidence_key)
                elif ksi.startswith('CED-'):
                    ksi_categories['Continuous Education (CED)'].append(evidence_key)
                elif ksi.startswith('RPL-'):
                    ksi_categories['Recovery Planning (RPL)'].append(evidence_key)
                elif ksi.startswith('INR-'):
                    ksi_categories['Incident Response (INR)'].append(evidence_key)
        else:
            evidence_without_requirements += 1
            print(f"❌ {evidence_key}: No requirements mapped")
    
    print(f"\n=== SUMMARY STATISTICS ===")
    print(f"Total evidence sets: {total_evidence_sets}")
    print(f"Evidence sets with requirements: {evidence_with_requirements}")
    print(f"Evidence sets without requirements: {evidence_without_requirements}")
    print(f"Coverage: {(evidence_with_requirements/total_evidence_sets)*100:.1f}%")
    
    print(f"\n=== KSI FREQUENCY ANALYSIS ===")
    print(f"Total unique KSIs found: {len(all_ksis)}")
    print("\nMost frequently mapped KSIs:")
    for ksi, count in sorted(ksi_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ksi}: {count} evidence sets")
    
    print(f"\n=== EVIDENCE SETS BY KSI CATEGORY ===")
    for category, evidence_list in sorted(ksi_categories.items()):
        unique_evidence = list(set(evidence_list))
        print(f"\n{category}:")
        for evidence in sorted(unique_evidence):
            print(f"  - {evidence}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze evidence-KSI mappings from evidence sets with requirements"
    )
    parser.add_argument(
        'evidence_sets_file',
        nargs='?',
        default='evidence_sets_with_requirements.json',
        help='Path to the evidence sets file with requirements (default: %(default)s)'
    )
    
    args = parser.parse_args()
    
    print("Loading evidence sets with requirements...")
    evidence_sets = load_evidence_sets(args.evidence_sets_file)
    
    analyze_mappings(evidence_sets)

if __name__ == "__main__":
    main()
