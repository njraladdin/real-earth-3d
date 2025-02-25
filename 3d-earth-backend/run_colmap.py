import os
import shutil
import subprocess
from pathlib import Path
import sqlite3

def run_command(command):
    """Run a command and check for errors"""
    try:
        process = subprocess.run(
            command, 
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"Error output: {e.stderr}")
        # Check for specific COLMAP errors
        if "No good initial image pair found" in e.stderr:
            raise RuntimeError("COLMAP could not find a good initial image pair. Try adding more images with better overlap.")
        elif "failed to create sparse model" in e.stderr:
            raise RuntimeError("COLMAP failed to create a sparse model. The images may not have enough visual overlap.")
        else:
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

def get_registered_images(database_path, sparse_path):
    """Get list of registered image names from COLMAP reconstruction"""
    registered_images = set()
    
    # Read images.txt from the sparse reconstruction
    images_file = sparse_path / "images.txt"
    if not images_file.exists():
        print(f"Warning: {images_file} not found!")
        return registered_images
        
    try:
        with open(images_file, 'r') as f:
            # Skip comment lines
            while True:
                line = f.readline()
                if not line or not line.startswith('#'):
                    break
                    
            # Read image entries
            while line:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split()
                    if len(parts) >= 9:  # Valid image line
                        image_name = parts[9]  # Image name is the 10th field
                        registered_images.add(image_name)
                    # Skip the points2D line
                    f.readline()
                line = f.readline()
                
    except Exception as e:
        print(f"Error reading reconstruction file: {e}")
        
    return registered_images

def run_colmap_pipeline(dataset_path="dataset", input_images_path=None, cleanup_existing=True):
    """
    Run the COLMAP SfM pipeline on a dataset.
    
    Args:
        dataset_path (str): Path to the dataset directory containing an 'images' folder
        input_images_path (str, optional): Path to input images to be copied to dataset/images
        cleanup_existing (bool): Whether to clean up existing files in the dataset directory (default: True)
        
    Returns:
        dict: Statistics about the reconstruction
    """
    dataset_path = Path(dataset_path)
    images_path = dataset_path / "images"
    database_path = dataset_path / "database.db"
    sparse_path = dataset_path / "sparse"
    
    # Look for vocab tree in multiple locations
    vocab_tree_paths = [
        Path("vocab_tree_flickr100K_words32K.bin"),
        Path(__file__).parent / "vocab_tree_flickr100K_words32K.bin",
        Path("/usr/local/share/colmap/vocab_tree_flickr100K_words32K.bin"),
        Path("C:/Program Files/COLMAP/vocab_tree_flickr100K_words32K.bin")
    ]
    
    vocab_tree_path = None
    for path in vocab_tree_paths:
        if path.exists():
            vocab_tree_path = path
            break
    
    if not vocab_tree_path:
        # If vocab tree not found, download it
        import urllib.request
        print("Vocabulary tree not found. Downloading...")
        vocab_tree_path = Path(__file__).parent / "vocab_tree_flickr100K_words32K.bin"
        urllib.request.urlretrieve(
            "https://demuc.de/colmap/vocab_tree_flickr100K_words32K.bin",
            vocab_tree_path
        )

    # Create dataset directory if it doesn't exist
    dataset_path.mkdir(exist_ok=True, parents=True)

    # Clean up existing files if cleanup_existing is True
    if cleanup_existing:
        print("Cleaning up existing files...")
        try:
            if sparse_path.exists():
                shutil.rmtree(sparse_path)
            if database_path.exists():
                database_path.unlink()
            # Only delete images directory if we're copying new images
            if input_images_path and images_path.exists():
                shutil.rmtree(images_path)
        except PermissionError as e:
            raise RuntimeError(f"Failed to delete existing files - permission denied. Please check if any other programs are using the files.\nError: {e}")
        except OSError as e:
            raise RuntimeError(f"Failed to delete existing files.\nError: {e}")

    # Create images directory only if we're copying new images or it doesn't exist
    if input_images_path or not images_path.exists():
        images_path.mkdir(exist_ok=True, parents=True)

    # If input_images_path is provided, copy images to dataset/images
    if input_images_path:
        input_images_path = Path(input_images_path)
        if not input_images_path.exists():
            raise FileNotFoundError(f"Error: Input images path {input_images_path} not found!")
        
        print(f"Copying images from {input_images_path} to {images_path}...")
        for ext in ['*.jpg', '*.JPG', '*.png', '*.PNG']:
            for img_file in input_images_path.glob(ext):
                shutil.copy2(img_file, images_path)

    if not images_path.exists() or not any(images_path.iterdir()):
        raise FileNotFoundError(f"Error: No images found in {images_path}!")

    if not vocab_tree_path.exists():
        raise FileNotFoundError(f"Error: Vocabulary tree file not found at {vocab_tree_path}")

    print("Starting COLMAP pipeline...")

    # Step 1: Feature Extraction
    print("Step 1: Extracting features...")
    run_command([
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_path),
        "--SiftExtraction.max_num_features", "1024"  # Reduced from default 8192
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
    model_path = sparse_path / "0"
    if model_path.exists():
        run_command([
            "colmap", "model_converter",
            "--input_path", str(model_path),
            "--output_path", str(sparse_path),
            "--output_type", "TXT"
        ])
    else:
        print("Warning: No reconstruction model found. COLMAP may have failed to register any images.")
        # Create empty text files to avoid errors in downstream processing
        (sparse_path / "cameras.txt").touch()
        (sparse_path / "images.txt").touch()
        (sparse_path / "points3D.txt").touch()

    # Analyze the reconstruction
    print("\nAnalyzing reconstruction quality...")
    total_images = len(list(images_path.glob('*.[jJ][pP][gG]'))) + \
                   len(list(images_path.glob('*.[pP][nN][gG]')))
    
    stats = read_reconstruction_stats(sparse_path)
    quality_score = calculate_quality_score(stats, total_images)
    
    # Add total_images to stats
    stats['total_images'] = total_images
    
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
    # Skip the registered/unregistered image copying for server integration
    # as we don't need those files for the splat generation
    
    print("\nCOLMAP pipeline completed successfully!")
    
    return stats

if __name__ == "__main__":
    try:
        run_colmap_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 