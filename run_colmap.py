import os
import shutil
import subprocess
from pathlib import Path

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
    stats = {}
    
    # Read cameras.txt to get number of registered images
    cameras_file = sparse_path / "cameras.txt"
    images_file = sparse_path / "images.txt"
    points_file = sparse_path / "points3D.txt"
    
    # Count registered images
    with open(images_file, 'r') as f:
        lines = f.readlines()
        # Every other line contains image info
        registered_images = sum(1 for line in lines if not line.startswith('#') and len(line.strip()) > 0) // 2
        stats['registered_images'] = registered_images
    
    # Count 3D points and track lengths
    total_points = 0
    total_observations = 0
    total_error = 0
    
    with open(points_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 4:  # Valid point3D line
                total_points += 1
                track_length = int(parts[6])
                error = float(parts[7])
                total_observations += track_length
                total_error += error
    
    stats['total_3d_points'] = total_points
    if total_points > 0:
        stats['average_track_length'] = total_observations / total_points
        stats['mean_reprojection_error'] = total_error / total_points
    if registered_images > 0:
        stats['average_observations_per_image'] = total_observations / registered_images
    
    return stats

def calculate_quality_score(stats, total_images):
    """
    Calculate an overall quality score (0-100) based on various metrics
    """
    score = 0
    
    # Registration score (0-30 points)
    registration_percentage = stats['registered_images'] / total_images
    score += min(30, registration_percentage * 30)
    
    # Track length score (0-25 points)
    # Normalize track length: 3 images = 10 points, 10+ images = 25 points
    track_length_score = min(25, max(0, (stats['average_track_length'] - 3) * (25 / 7)))
    score += track_length_score
    
    # Reprojection error score (0-25 points)
    # 2.0 pixels = 10 points, 1.0 pixels = 25 points
    error_score = min(25, max(0, 25 - (stats['mean_reprojection_error'] - 1.0) * 15))
    score += error_score
    
    # Points per image score (0-20 points)
    # 1000 points = 10 points, 5000+ points = 20 points
    points_per_image = stats['average_observations_per_image']
    points_score = min(20, max(0, 10 + (points_per_image - 1000) * (10 / 4000)))
    score += points_score
    
    return round(score, 1)

def run_colmap_pipeline(dataset_path="dataset"):
    """
    Run the COLMAP SfM pipeline on a dataset.
    
    Args:
        dataset_path (str): Path to the dataset directory containing an 'images' folder
    """
    # Convert to Path object for easier path manipulation
    dataset_path = Path(dataset_path)
    images_path = dataset_path / "images"
    database_path = dataset_path / "database.db"
    sparse_path = dataset_path / "sparse"

    # Check if images directory exists
    if not images_path.exists():
        raise FileNotFoundError(f"Error: {images_path} folder not found!")

    print("Starting COLMAP pipeline...")

    # Clean up existing files
    print("Cleaning up existing files...")
    if sparse_path.exists():
        shutil.rmtree(sparse_path)
    if database_path.exists():
        database_path.unlink()

    # Step 1: Feature Extraction
    print("Step 1: Extracting features...")
    run_command([
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_path)
    ])

    # Step 2: Feature Matching
    print("Step 2: Matching features...")
    run_command([
        "colmap", "exhaustive_matcher",
        "--database_path", str(database_path)
    ])

    # Step 3: Create output folder for sparse reconstruction
    print("Step 3: Creating sparse reconstruction folder...")
    sparse_path.mkdir(exist_ok=True)

    # Step 4: Sparse Reconstruction (Mapper)
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

    # After the pipeline completes, analyze the reconstruction
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
    print(f"Mean reprojection error: {stats['mean_reprojection_error']:.2f} pixels")
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
    if stats['mean_reprojection_error'] > 2.0:
        warnings.append("High mean reprojection error (> 2.0 pixels)")
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    print("\nCOLMAP pipeline completed successfully!")
    
    return stats

if __name__ == "__main__":
    try:
        run_colmap_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 