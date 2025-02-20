import os
import subprocess
from pathlib import Path
import shutil

def run_command(command):
    """Run a command and check for errors"""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        raise e

def extract_image_names(images_txt_path):
    """Extract image names from a COLMAP images.txt file"""
    image_names = []
    with open(images_txt_path, 'r') as f:
        lines = f.readlines()
        # Skip header lines
        for line in lines[4::2]:  # images.txt has 2 lines per image, we want the first line
            parts = line.strip().split()
            if len(parts) >= 2:
                image_name = parts[9]  # Image name is the last field
                image_names.append(image_name)
    return image_names

def register_new_images(main_model_path, staging_model_path, database_path, output_path):
    """
    Register staging images into the main COLMAP reconstruction.
    """
    main_model_path = Path(main_model_path)
    staging_model_path = Path(staging_model_path)
    output_path = Path(output_path)
    merged_dataset_root = output_path.parent.parent

    # Create output directory structure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy main model to output location as starting point
    if output_path.exists():
        shutil.rmtree(output_path)
    shutil.copytree(main_model_path, output_path)

    # Copy database.db to merged dataset
    merged_db_path = merged_dataset_root / "database.db"
    shutil.copy2(database_path, merged_db_path)

    # Create and populate images directory
    merged_images_dir = merged_dataset_root / "images"
    merged_images_dir.mkdir(exist_ok=True)
    
    # Copy images from main dataset
    main_images_dir = Path("dataset_main/images")
    for img in main_images_dir.glob("*"):
        shutil.copy2(img, merged_images_dir)
    
    # Copy images from staging dataset
    staging_images_dir = Path("dataset_staging/images")
    for img in staging_images_dir.glob("*"):
        shutil.copy2(img, merged_images_dir)

    # Get list of new images from staging
    staging_images = extract_image_names(staging_model_path.parent / "images.txt")
    temp_image_list = Path("temp_image_list.txt")
    with open(temp_image_list, 'w') as f:
        for image_name in staging_images:
            f.write(f"{image_name}\n")

    try:
        print("Extracting features for staging images...")
        run_command([
            "colmap", "feature_extractor",
            "--database_path", str(merged_db_path),
            "--image_path", str(merged_images_dir),
            "--image_list_path", str(temp_image_list),
            "--SiftExtraction.max_num_features", "1024"
        ])

        print("Matching staging images against main model...")
        run_command([
            "colmap", "vocab_tree_matcher",
            "--database_path", str(merged_db_path),
            "--VocabTreeMatching.vocab_tree_path", "vocab_tree_flickr100K_words32K.bin",
            "--VocabTreeMatching.match_list_path", str(temp_image_list)
        ])

        print("Registering staging images into the merged model...")
        run_command([
            "colmap", "image_registrator",
            "--database_path", str(merged_db_path),
            "--input_path", str(main_model_path),
            "--output_path", str(output_path)
        ])

        print("Running bundle adjustment...")
        run_command([
            "colmap", "bundle_adjuster",
            "--input_path", str(output_path),
            "--output_path", str(output_path)
        ])

        # Convert to TXT format
        print("Converting merged model to TXT format...")
        run_command([
            "colmap", "model_converter",
            "--input_path", str(output_path),
            "--output_path", str(output_path.parent),
            "--output_type", "TXT"
        ])

        print("Registration completed successfully!")
        print(f"Merged model saved at: {output_path}")

    finally:
        if temp_image_list.exists():
            temp_image_list.unlink()

def main():
    try:
        register_new_images(
            main_model_path="dataset_main/sparse/0",      # Path to main model
            staging_model_path="dataset_staging/sparse/0", # Path to staging model
            database_path="dataset_main/database.db",     # Path to main database
            output_path="dataset_merged/sparse/0"         # Path for merged output
        )
        print("\nMerged dataset structure created at dataset_merged/:")
        print("  - sparse/0/      : Merged COLMAP reconstruction")
        print("  - database.db    : Copied and updated database")
        print("  - images/        : Combined images from both datasets")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 