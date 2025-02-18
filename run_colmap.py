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

    print("COLMAP pipeline completed successfully!")

if __name__ == "__main__":
    try:
        run_colmap_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 