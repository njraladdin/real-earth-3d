import os
import shutil
import subprocess
from pathlib import Path
import sqlite3

def run_command(command):
    """Run a command and check for errors"""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        raise e

def read_reconstruction_stats(sparse_path):
    """
    Read and analyze the COLMAP reconstruction from text files.
    Returns a dictionary of quality metrics.
    """
    stats = {'registered_images': 0, 'total_3d_points': 0, 'total_observations': 0}
    
    images_file = sparse_path / "images.txt"
    points_file = sparse_path / "points3D.txt"
    
    if not images_file.exists():
        print(f"Warning: {images_file} not found!")
        return stats
        
    print("\nDEBUG: Reading reconstruction files...")
    
    # First count the number of images by reading header lines
    image_count = 0
    total_observations = 0
    
    with open(images_file, 'r') as f:
        # Skip the header comment lines
        while True:
            line = f.readline()
            if not line or not line.startswith('#'):
                break
                
        # Now read the actual data
        while line:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split()
                if len(parts) >= 10:  # Image line
                    image_count += 1
                    # Read the points line
                    points_line = f.readline()
                    if points_line:
                        points = points_line.strip().split()
                        num_observations = len(points) // 3
                        total_observations += num_observations
                        print(f"DEBUG: Image {image_count} has {num_observations} observations")
            line = f.readline()
    
    # Count 3D points
    point_count = 0
    if points_file.exists():
        with open(points_file, 'r') as f:
            # Skip header
            while True:
                line = f.readline()
                if not line or not line.startswith('#'):
                    break
            # Count points
            while line:
                if line.strip() and not line.startswith('#'):
                    point_count += 1
                line = f.readline()
        print(f"DEBUG: Found {point_count} 3D points")
    else:
        print(f"Warning: {points_file} not found!")
    
    stats['registered_images'] = image_count
    stats['total_3d_points'] = point_count
    stats['total_observations'] = total_observations
    
    if image_count > 0 and point_count > 0:
        stats['average_track_length'] = total_observations / point_count
        stats['average_observations_per_image'] = total_observations / image_count
    else:
        stats['average_track_length'] = 0
        stats['average_observations_per_image'] = 0
    
    return stats

def calculate_quality_score(stats, total_images):
    """
    Calculate an overall quality score (0-100) based on various metrics
    """
    score = 0
    
    # Registration score (0-40 points) - increased weight
    registration_percentage = stats['registered_images'] / total_images
    score += min(40, registration_percentage * 40)  # More weight on registration
    
    # Only calculate other metrics if we have enough registered images
    if registration_percentage < 0.3:  # If less than 30% images registered
        return score  # Return just the registration score
    
    # Track length score (0-20 points) - decreased weight
    track_length_score = min(20, max(0, (stats['average_track_length'] - 3) * (20 / 7)))
    score += track_length_score
    
    # Reprojection error score (0-20 points) - decreased weight
    error_score = min(20, max(0, 20 - (stats['average_track_length'] - 1.0) * 15))
    score += error_score
    
    # Points per image score (0-20 points)
    points_per_image = stats['average_observations_per_image']
    points_score = min(20, max(0, 10 + (points_per_image - 1000) * (10 / 4000)))
    score += points_score
    
    return round(score, 1)

def sort_images_by_location(sparse_path, dataset_path, output_path, sort_method='path'):
    """
    Sort images based on their physical location from COLMAP reconstruction.
    
    Args:
        sparse_path (Path): Path to the sparse reconstruction folder
        dataset_path (Path): Path to the original dataset folder
        output_path (Path): Path where sorted images will be saved
        sort_method (str): Sorting method to use:
            'distance' - sort by distance from origin
            'path' - sort by trying to find a continuous path
            'x' - sort by X coordinate
            'y' - sort by Y coordinate
            'z' - sort by Z coordinate
    """
    images_txt = sparse_path / "images.txt"
    if not images_txt.exists():
        print("Warning: images.txt not found! Cannot sort images.")
        return
        
    output_path.mkdir(exist_ok=True)
    
    # Read and parse images.txt
    images = []
    with open(images_txt, 'r') as f:
        while True:
            line = f.readline()
            if not line or not line.startswith('#'):
                break
                
        while line:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split()
                if len(parts) >= 10:  # Image line
                    image_name = parts[-1]
                    tx, ty, tz = map(float, parts[5:8])  # Extract position
                    images.append((image_name, tx, ty, tz))
                    f.readline()  # Skip points line
            line = f.readline()
    
    if not images:
        print("No images found in reconstruction!")
        return

    # Sort images based on selected method
    if sort_method == 'distance':
        # Sort by distance from origin
        sorted_images = sorted(images, 
            key=lambda x: (x[1]**2 + x[2]**2 + x[3]**2)**0.5)
    
    elif sort_method == 'path':
        # Try to find a continuous path through the cameras
        sorted_images = [images[0]]  # Start with first image
        remaining = images[1:]
        
        while remaining:
            last = sorted_images[-1]
            # Find closest remaining image to the last one
            closest = min(remaining, 
                key=lambda x: ((x[1]-last[1])**2 + 
                             (x[2]-last[2])**2 + 
                             (x[3]-last[3])**2)**0.5)
            sorted_images.append(closest)
            remaining.remove(closest)
    
    elif sort_method in ['x', 'y', 'z']:
        # Sort by specific coordinate
        coord_idx = {'x': 1, 'y': 2, 'z': 3}[sort_method]
        sorted_images = sorted(images, key=lambda x: x[coord_idx])
    
    else:
        print(f"Unknown sort method: {sort_method}")
        return

    # Copy images with new sorted names
    for idx, (image_name, *_) in enumerate(sorted_images, 1):
        original_path = dataset_path / "images" / image_name
        ext = original_path.suffix
        new_name = f"image_{idx:04d}{ext}"
        shutil.copy2(original_path, output_path / new_name)
        print(f"Copied {image_name} -> {new_name}")

    print(f"\nSorted {len(sorted_images)} images using '{sort_method}' method")

def run_colmap_pipeline(dataset_path="dataset"):
    """
    Run the COLMAP SfM pipeline on a dataset.
    
    Args:
        dataset_path (str): Path to the dataset directory containing an 'images' folder
    """
    dataset_path = Path(dataset_path)
    images_path = dataset_path / "images"
    database_path = dataset_path / "database.db"
    sparse_path = dataset_path / "sparse"
    vocab_tree_path = Path("vocab_tree_flickr100K_words32K.bin")

    if not images_path.exists():
        raise FileNotFoundError(f"Error: {images_path} folder not found!")

    if not vocab_tree_path.exists():
        raise FileNotFoundError(f"Error: Vocabulary tree file not found at {vocab_tree_path}")

    print("Starting COLMAP pipeline...")

    # Clean up existing files
    print("Cleaning up existing files...")
    try:
        if sparse_path.exists():
            shutil.rmtree(sparse_path)
        if database_path.exists():
            database_path.unlink()
    except PermissionError as e:
        raise RuntimeError(f"Failed to delete existing files - permission denied. Please check if any other programs are using the files.\nError: {e}")
    except OSError as e:
        raise RuntimeError(f"Failed to delete existing files.\nError: {e}")

    # Step 1: Feature Extraction
    print("Step 1: Extracting features...")
    run_command([
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_path)
    ])

    # Step 2: Feature Matching using Vocabulary Tree
    print("Step 2: Matching features using vocabulary tree...")
    run_command([
        "colmap", "vocab_tree_matcher",
        "--database_path", str(database_path),
        "--VocabTreeMatching.vocab_tree_path", str(vocab_tree_path),
        "--VocabTreeMatching.num_images", "100",  # Number of nearest neighbors to match
        "--VocabTreeMatching.num_nearest_neighbors", "50"  # Number of nearest visual words to match
    ])

    # After feature matching, add:
    print("\nAnalyzing matches before reconstruction...")

    # Step 3: Create output folder for sparse reconstruction
    print("Step 3: Creating sparse reconstruction folder...")
    sparse_path.mkdir(exist_ok=True)

    # Step 4: Mapper with modified parameters
    print("Step 4: Running mapper for sparse reconstruction...")
    run_command([
        "colmap", "mapper",
        "--database_path", str(database_path),
        "--image_path", str(images_path),
        "--output_path", str(sparse_path)
    ])

    # Step 5: Convert the model to TXT format
    print("Step 5: Converting model to TXT format...")
    run_command([
        "colmap", "model_converter",
        "--input_path", str(sparse_path / "0"),
        "--output_path", str(sparse_path),
        "--output_type", "TXT"
    ])

    # Analyze the reconstruction
    print("\nAnalyzing reconstruction quality...")
    total_images = len(list(images_path.glob('*.[jJ][pP][gG]'))) + \
                   len(list(images_path.glob('*.[pP][nN][gG]')))
    
    stats = read_reconstruction_stats(sparse_path)
    quality_score = calculate_quality_score(stats, total_images)
    
    print("\nReconstruction Quality Metrics:")
    print(f"Total images in dataset: {total_images}")
    print(f"Registered images: {stats['registered_images']} ({(stats['registered_images']/total_images)*100:.1f}%)")
    print(f"Number of 3D points: {stats['total_3d_points']:,}")
    print(f"Average track length: {stats['average_track_length']:.2f} images per 3D point")
    print(f"Average observations per image: {stats['average_observations_per_image']:.2f} points per image")
    print(f"\nOverall Quality Score: {quality_score}/100")
    
    if quality_score >= 90:
        print("📸 Excellent reconstruction quality!")
    elif quality_score >= 75:
        print("✨ Good reconstruction quality")
    elif quality_score >= 60:
        print("👍 Acceptable reconstruction quality")
    else:
        print("⚠️ Poor reconstruction quality")
    
    # You might want to consider the reconstruction poor if:
    warnings = []
    if stats['registered_images'] / total_images < 0.8:
        warnings.append("Less than 80% of images were registered!")
    if stats['average_track_length'] < 3:
        warnings.append("Average track length is low (< 3 images per point)")
    if stats['average_track_length'] > 7:
        warnings.append("Average track length is high (> 7 images per point)")
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    print("\nCOLMAP pipeline completed successfully!")
    
    # Add sorting functionality
    print("\nSorting images by physical location...")
    sorted_images_path = Path(dataset_path) / "sorted_images"
    # Try the 'path' method which often gives better results
    sort_images_by_location(sparse_path, Path(dataset_path), sorted_images_path, 
                          sort_method='path')
    
    return stats

if __name__ == "__main__":
    try:
        run_colmap_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 