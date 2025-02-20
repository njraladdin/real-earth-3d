import os
import shutil
import subprocess
from pathlib import Path
from run_colmap import run_command, read_reconstruction_stats, calculate_quality_score

def merge_new_images(dataset_path="dataset", new_images_path="new_images"):
    """
    Merge new images into an existing COLMAP reconstruction.
    
    Args:
        dataset_path (str): Path to the existing dataset directory containing 'images', 'sparse', and database.db
        new_images_path (str): Path to the folder containing new images to merge
    """
    # Convert to Path objects
    dataset_path = Path(dataset_path)
    new_images_path = Path(new_images_path)
    images_path = dataset_path / "images"
    database_path = dataset_path / "database.db"
    sparse_path = dataset_path / "sparse"
    
    # Validate paths
    if not new_images_path.exists():
        raise FileNotFoundError(f"Error: {new_images_path} folder not found!")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Error: {dataset_path} folder not found!")
    if not database_path.exists():
        raise FileNotFoundError(f"Error: No existing COLMAP database found at {database_path}")
    if not sparse_path.exists():
        raise FileNotFoundError(f"Error: No existing sparse reconstruction found at {sparse_path}")

    print("Starting COLMAP image merging pipeline...")

    # Copy new images to the dataset, but skip existing ones
    print("Copying new images to dataset...")
    new_image_files = []
    for ext in ('*.jpg', '*.JPG', '*.png', '*.PNG'):
        new_image_files.extend(list(new_images_path.glob(ext)))
    
    if not new_image_files:
        raise ValueError(f"No images found in {new_images_path}")
    
    # Track which images are actually new
    actually_new_images = []
    for image_file in new_image_files:
        target_path = images_path / image_file.name
        if not target_path.exists():
            shutil.copy2(image_file, images_path)
            actually_new_images.append(image_file)
        else:
            print(f"Skipping {image_file.name} - already exists in dataset")
    
    if not actually_new_images:
        raise ValueError("No new images to add - all images already exist in dataset")
    
    print(f"Copied {len(actually_new_images)} new images to dataset")

    # Extract features for new images only
    print("Extracting features for new images...")
    
    # Create a image list file containing only the new image names
    image_list_file = dataset_path / "new_image_list.txt"
    with open(image_list_file, 'w') as f:
        for image_file in actually_new_images:
            f.write(f"{image_file.name}\n")
    
    run_command([
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_path),
        "--image_list_path", str(image_list_file)
    ])

    # Clean up the temporary file
    image_list_file.unlink()

    # Match new images against existing reconstruction
    print("Matching new features...")
    run_command([
        "colmap", "exhaustive_matcher",
        "--database_path", str(database_path),
        "--SiftMatching.guided_matching", "1"
    ])

    # Backup existing sparse reconstruction
    backup_path = sparse_path.parent / "sparse_backup"
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.copytree(sparse_path, backup_path)
    print(f"Backed up existing reconstruction to {backup_path}")

    # Run mapper to merge new images into existing reconstruction
    print("Running mapper to merge new images...")
    run_command([
        "colmap", "mapper",
        "--database_path", str(database_path),
        "--image_path", str(images_path),
        "--input_path", str(sparse_path / "0"),
        "--output_path", str(sparse_path)
    ])

    # Convert the updated model to TXT format
    print("Converting updated model to TXT format...")
    run_command([
        "colmap", "model_converter",
        "--input_path", str(sparse_path / "0"),
        "--output_path", str(sparse_path),
        "--output_type", "TXT"
    ])

    # Analyze the updated reconstruction
    print("\nAnalyzing updated reconstruction quality...")
    total_images = len(list(images_path.glob('*.[jJ][pP][gG]'))) + \
                   len(list(images_path.glob('*.[pP][nN][gG]')))
    
    stats = read_reconstruction_stats(sparse_path)
    quality_score = calculate_quality_score(stats, total_images)
    
    print("\nUpdated Reconstruction Metrics:")
    print(f"Total images in dataset: {total_images}")
    print(f"Registered images: {stats['registered_images']} ({(stats['registered_images']/total_images)*100:.1f}%)")
    print(f"Number of 3D points: {stats['total_3d_points']:,}")
    print(f"Average track length: {stats['average_track_length']:.2f} images per 3D point")
    print(f"Average observations per image: {stats['average_observations_per_image']:.2f} points per image")
    print(f"Mean reprojection error: {stats['mean_reprojection_error']:.2f} pixels")
    print(f"\nOverall Quality Score: {quality_score}/100")

    print("\nImage merging completed successfully!")
    return stats

if __name__ == "__main__":
    try:
        merge_new_images()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 