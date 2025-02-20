import sqlite3
import numpy as np
from pathlib import Path
import subprocess
import shutil
from collections import defaultdict
import networkx as nx

def run_colmap_command(cmd):
    """Run a COLMAP command and check for errors"""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"COLMAP command failed: {' '.join(cmd)}")
        raise e

def extract_colmap_features(image_dir, database_path, gpu_index=-1):
    """Extract SIFT features using COLMAP"""
    print("Extracting features with COLMAP...")
    
    # Remove existing database if it exists
    database_path.unlink(missing_ok=True)
    
    # Feature extraction - simplified to match run_colmap.py approach
    cmd = [
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(image_dir),
        "--ImageReader.single_camera", "1",
        # Remove explicit GPU flags to use COLMAP defaults
        "--SiftExtraction.max_num_features", "8192",
        "--SiftExtraction.max_image_size", "2048"
    ]
    
    run_colmap_command(cmd)

def match_colmap_features(database_path, gpu_index=-1):
    """Perform exhaustive matching of features"""
    print("Matching features...")
    
    # Simplified matching command to match run_colmap.py approach
    cmd = [
        "colmap", "exhaustive_matcher",
        "--database_path", str(database_path)
    ]
    
    run_colmap_command(cmd)

def get_image_matches(database_path, min_matches=20):
    """Extract image matches from COLMAP database"""
    print("Reading matches from database...")
    
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    # Get total number of images
    cursor.execute("SELECT COUNT(*) FROM images;")
    total_images = cursor.fetchone()[0]
    print(f"\nTotal images in database: {total_images}")
    
    # Get image names and IDs
    cursor.execute("SELECT image_id, name FROM images;")
    image_ids = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Get all matches to analyze distribution
    cursor.execute("SELECT pair_id, rows FROM two_view_geometries;")
    all_matches = cursor.fetchall()
    
    print(f"\nFound {len(all_matches)} image pairs with matches")
    if all_matches:
        match_counts = [count for _, count in all_matches]
        print(f"Match statistics:")
        print(f"  Min matches: {min(match_counts)}")
        print(f"  Max matches: {max(match_counts)}")
        print(f"  Avg matches: {sum(match_counts)/len(match_counts):.1f}")
    
    # Get filtered matches
    cursor.execute("SELECT pair_id, rows FROM two_view_geometries WHERE rows >= ?;", (min_matches,))
    
    matches = defaultdict(list)
    filtered_pairs = 0
    for pair_id, num_matches in cursor.fetchall():
        # Decode pair_id to get image IDs
        image_id1 = pair_id >> 32
        image_id2 = pair_id & ((1 << 32) - 1)
        
        if image_id1 in image_ids and image_id2 in image_ids:
            matches[image_ids[image_id1]].append((image_ids[image_id2], num_matches))
            matches[image_ids[image_id2]].append((image_ids[image_id1], num_matches))
            filtered_pairs += 1
    
    print(f"\nAfter filtering (min_matches={min_matches}):")
    print(f"  Retained {filtered_pairs} image pairs")
    print(f"  Images with matches: {len(matches)}")
    
    conn.close()
    return matches

def group_images_by_connectivity(matches, min_group_size=2):
    """Group images based on their feature matches using graph connectivity"""
    print("\nGrouping images based on feature matches...")
    
    # Create a graph where nodes are images and edges represent matches
    G = nx.Graph()
    
    # Add edges between matching images and track match counts
    edge_weights = []
    for img1, connected_images in matches.items():
        for img2, num_matches in connected_images:
            G.add_edge(img1, img2, weight=num_matches)
            edge_weights.append(num_matches)
    
    if edge_weights:
        print(f"\nMatch statistics for connected images:")
        print(f"  Min matches between pairs: {min(edge_weights)}")
        print(f"  Max matches between pairs: {max(edge_weights)}")
        print(f"  Avg matches between pairs: {sum(edge_weights)/len(edge_weights):.1f}")
    
    # Find connected components (groups of related images)
    groups = list(nx.connected_components(G))
    
    print(f"\nFound {len(groups)} groups before filtering:")
    for i, group in enumerate(groups):
        print(f"Group {i}: {len(group)} images")
        # Print some example matches within the group
        if len(group) > 1:
            group_list = list(group)
            print("  Example matches:")
            for j in range(min(3, len(group_list))):
                for k in range(j+1, min(4, len(group_list))):
                    if G.has_edge(group_list[j], group_list[k]):
                        weight = G[group_list[j]][group_list[k]]['weight']
                        print(f"    {group_list[j]} <-> {group_list[k]}: {weight} matches")
    
    # Filter out small groups
    filtered_groups = [group for group in groups if len(group) >= min_group_size]
    
    if len(filtered_groups) < len(groups):
        print(f"\nRemoved {len(groups) - len(filtered_groups)} groups smaller than {min_group_size} images")
    
    return filtered_groups

def group_images_in_colmap(input_path, output_path, min_matches=200, min_group_size=2, gpu_index=-1):
    """
    Group images based on shared COLMAP features
    
    Args:
        input_path: Path to directory containing input images
        output_path: Path to output directory for grouped images
        min_matches: Minimum number of feature matches (increased to 200)
        min_group_size: Minimum number of images in a group
        gpu_index: GPU index to use (-1 for CPU)
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    database_path = input_path.parent / "database.db"
    
    # Clear and create output directory
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True)
    
    # Extract and match features using COLMAP
    extract_colmap_features(input_path, database_path, gpu_index)
    match_colmap_features(database_path, gpu_index)
    
    # Get matches between images
    matches = get_image_matches(database_path, min_matches)
    
    # Group images based on matches
    groups = group_images_by_connectivity(matches, min_group_size)
    
    # Copy images to group folders
    print("\nCopying images to group folders...")
    for i, group in enumerate(groups):
        group_dir = output_path / f"group_{i}"
        group_dir.mkdir(exist_ok=True)
        
        print(f"\nGroup {i}: {len(group)} images")
        for img_name in group:
            src = input_path / img_name
            dst = group_dir / img_name
            shutil.copy2(src, dst)
            print(f"  Copied {img_name}")
    
    print(f"\nImages grouped into {len(groups)} categories")
    print(f"Results saved in: {output_path}")
    
    # Cleanup
    database_path.unlink(missing_ok=True)
    
    return groups

if __name__ == "__main__":
    dataset_path = Path("dataset")
    input_path = dataset_path / "images"
    output_path = dataset_path / "grouped_images_colmap"
    
    if not input_path.exists():
        print(f"Error: Input directory not found: {input_path}")
        exit(1)
    
    try:
        group_images_in_colmap(
            input_path,
            output_path,
            min_matches=200,  # Minimum matches between images to consider them related
            min_group_size=2,  # Minimum images in a group
            gpu_index=0  # Use first GPU, set to -1 for CPU
        )
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 