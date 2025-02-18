import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_splat_results(
    opensplat_dir="OpenSplat",
    dataset_dir="dataset",
    backup_root="good_splats"
):
    """
    Backup OpenSplat results and dataset to a timestamped folder.
    
    Args:
        opensplat_dir (str): Path to OpenSplat directory
        dataset_dir (str): Path to dataset directory
        backup_root (str): Path to backup root directory
    """
    # Convert all paths to Path objects
    opensplat_path = Path(opensplat_dir)
    dataset_path = Path(dataset_dir)
    backup_root_path = Path(backup_root)

    # Check if required paths exist
    splat_path = opensplat_path / "build" / "Release" / "splat.ply"
    if not splat_path.exists():
        raise FileNotFoundError(f"Splat file not found at: {splat_path}")
    
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset directory not found at: {dataset_path}")

    # Create backup root directory if it doesn't exist
    backup_root_path.mkdir(exist_ok=True)

    # Create timestamped folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = backup_root_path / timestamp
    backup_folder.mkdir()

    print(f"Creating backup in: {backup_folder}")

    # Copy splat file
    print("Copying splat file...")
    shutil.copy2(splat_path, backup_folder / "splat.ply")

    # Copy dataset folder
    print("Copying dataset folder...")
    shutil.copytree(dataset_path, backup_folder / "dataset")

    print(f"Backup completed successfully in: {backup_folder}")
    return backup_folder

if __name__ == "__main__":
    try:
        backup_folder = backup_splat_results()
        print(f"Backup created in: {backup_folder}")
    except Exception as e:
        print(f"Error during backup: {e}")
        exit(1) 