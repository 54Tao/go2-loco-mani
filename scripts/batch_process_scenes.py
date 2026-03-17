#!/usr/bin/env python3
"""
Batch process SAGE scenes to extract metadata and generate robot spawn configurations.
This script analyzes multiple SAGE scenes without launching Isaac Sim.
"""

import json
import os
import zipfile
import yaml
from pathlib import Path
from typing import Dict, List
import argparse

def extract_scene_metadata(scene_zip_path: str) -> Dict:
    """Extract metadata from a SAGE scene zip file."""

    scene_name = Path(scene_zip_path).stem

    try:
        with zipfile.ZipFile(scene_zip_path, 'r') as zip_ref:
            # Find JSON file
            json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
            if not json_files:
                return None

            # Read JSON
            with zip_ref.open(json_files[0]) as f:
                scene_data = json.load(f)

            # Extract metadata
            metadata = {
                'scene_name': scene_name,
                'scene_id': scene_data.get('id', 'unknown'),
                'rooms': []
            }

            for room in scene_data.get('rooms', []):
                room_info = {
                    'room_id': room['id'],
                    'room_type': room['room_type'],
                    'dimensions': room['dimensions'],
                    'num_objects': len(room.get('objects', [])),
                    'num_walls': len(room.get('walls', [])),
                    'num_doors': len(room.get('doors', [])),
                }

                # Calculate potential spawn positions
                dims = room['dimensions']
                spawn_positions = generate_spawn_positions(dims)
                room_info['spawn_positions'] = spawn_positions

                metadata['rooms'].append(room_info)

            return metadata

    except Exception as e:
        print(f"Error processing {scene_name}: {e}")
        return None

def generate_spawn_positions(dimensions: Dict) -> List[Dict]:
    """Generate potential robot spawn positions based on room dimensions."""

    width = dimensions['width']
    length = dimensions['length']
    height = dimensions.get('height', 2.7)

    spawn_height = 0.5  # Robot spawn height

    positions = [
        {
            'name': 'center',
            'position': [width / 2, length / 2, spawn_height],
            'rotation': [0, 0, 0, 1],
            'description': '房间中央'
        },
        {
            'name': 'near_entrance',
            'position': [width / 2, length * 0.2, spawn_height],
            'rotation': [0, 0, 0, 1],
            'description': '靠近入口'
        },
        {
            'name': 'corner_1',
            'position': [width * 0.2, length * 0.2, spawn_height],
            'rotation': [0, 0, 0.707, 0.707],
            'description': '角落1'
        },
        {
            'name': 'corner_2',
            'position': [width * 0.8, length * 0.8, spawn_height],
            'rotation': [0, 0, -0.707, 0.707],
            'description': '角落2'
        }
    ]

    return positions

def batch_process_scenes(scenes_dir: str, output_file: str, max_scenes: int = None):
    """Process multiple SAGE scenes and generate configuration."""

    scenes_path = Path(scenes_dir)
    zip_files = sorted(scenes_path.glob('*.zip'))

    if max_scenes:
        zip_files = zip_files[:max_scenes]

    print(f"Processing {len(zip_files)} scenes...")

    all_metadata = []
    successful = 0
    failed = 0

    for i, zip_file in enumerate(zip_files):
        print(f"[{i+1}/{len(zip_files)}] Processing {zip_file.name}...", end=' ')

        metadata = extract_scene_metadata(str(zip_file))
        if metadata:
            all_metadata.append(metadata)
            successful += 1
            print("✓")
        else:
            failed += 1
            print("✗")

    # Generate YAML configuration
    config = {
        'dataset': 'SAGE-10k',
        'total_scenes': len(zip_files),
        'successful': successful,
        'failed': failed,
        'robot': {
            'model': 'go2_x5',
            'usd_path': '/home/tjz/go2_loco_mani/assets/go2_x5.usd',
            'num_joints': 18,
            'base_height': 0.4
        },
        'physics': {
            'gravity': -9.81,
            'time_step': 0.01,
            'solver_iterations': 4
        },
        'scenes': {}
    }

    # Add scene configurations
    for metadata in all_metadata:
        scene_name = metadata['scene_name']
        config['scenes'][scene_name] = {
            'scene_id': metadata['scene_id'],
            'rooms': metadata['rooms']
        }

    # Save to YAML
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\n✓ Configuration saved to: {output_file}")
    print(f"  Total scenes: {len(zip_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")

    # Generate summary statistics
    total_rooms = sum(len(m['rooms']) for m in all_metadata)
    room_types = {}
    for metadata in all_metadata:
        for room in metadata['rooms']:
            rt = room['room_type']
            room_types[rt] = room_types.get(rt, 0) + 1

    print(f"\nStatistics:")
    print(f"  Total rooms: {total_rooms}")
    print(f"  Room types: {len(room_types)}")
    print(f"  Top 5 room types:")
    for rt, count in sorted(room_types.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"    - {rt}: {count}")

def main():
    parser = argparse.ArgumentParser(description="Batch process SAGE scenes")
    parser.add_argument("--scenes_dir", type=str,
                       default="/home/tjz/go2_loco_mani/datasets/sage-10k/scenes",
                       help="Directory containing scene ZIP files")
    parser.add_argument("--output", type=str,
                       default="/home/tjz/go2_loco_mani/configs/batch_scene_configs.yaml",
                       help="Output YAML configuration file")
    parser.add_argument("--max_scenes", type=int, default=None,
                       help="Maximum number of scenes to process (for testing)")

    args = parser.parse_args()

    print("=" * 60)
    print("SAGE Scene Batch Processing")
    print("=" * 60)
    print(f"Scenes directory: {args.scenes_dir}")
    print(f"Output file: {args.output}")
    print()

    batch_process_scenes(args.scenes_dir, args.output, args.max_scenes)

    print("\n✓ Batch processing complete!")

if __name__ == "__main__":
    main()
