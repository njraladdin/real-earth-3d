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

def register_new_images(main_model_path, new_images_path, database_path, output_path):
    """
    Register new images into an existing COLMAP reconstruction.
    
    Args:
        main_model_path (str): Path to existing model's sparse reconstruction
        new_images_path (str): Path to directory containing new images to register
        database_path (str): Path to the database file
        output_path (str): Path where updated model will be saved
    """
    main_model_path = Path(main_model_path)
    new_images_path = Path(new_images_path)
    output_path = Path(output_path)
    database_path = Path(database_path)

    # Setup merged dataset paths
    merged_dataset_path = output_path.parent.parent  # Get dataset_merged folder
    merged_images_path = merged_dataset_path / "images"
    merged_database_path = merged_dataset_path / "database.db"

    # Create output directories
    output_path.mkdir(parents=True, exist_ok=True)
    merged_images_path.mkdir(parents=True, exist_ok=True)

    # Copy main database to merged location
    print(f"Copying database to {merged_database_path}")
    shutil.copy2(database_path, merged_database_path)

    # Copy all images to merged location
    print("Copying images to merged dataset...")
    main_images_path = Path("dataset_main/images")
    for img in main_images_path.glob("*"):
        if img.is_file():
            shutil.copy2(img, merged_images_path)
    for img in new_images_path.glob("*"):
        if img.is_file():
            shutil.copy2(img, merged_images_path)

    # Verify paths exist
    if not main_model_path.exists():
        raise FileNotFoundError(f"Main model path does not exist: {main_model_path}")
    if not new_images_path.exists():
        raise FileNotFoundError(f"New images directory not found: {new_images_path}")
    if not database_path.exists():
        raise FileNotFoundError(f"Database file not found: {database_path}")
    
    # Get list of new images directly from the images directory
    image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
    new_images = [f.name for f in new_images_path.iterdir() 
                 if f.suffix.lower() in image_extensions]
    
    if not new_images:
        raise ValueError(f"No images found in {new_images_path}")
    
    # Create temporary file with list of new images
    temp_image_list = Path("temp_image_list.txt")
    with open(temp_image_list, 'w') as f:
        for image_name in new_images:
            f.write(f"{image_name}\n")
    
    try:
        print(f"Found {len(new_images)} new images to register")
        
        # Step 1: Extract features for new images
        print("Extracting features for new images...")
        run_command([
            "colmap", "feature_extractor",
            "--database_path", str(merged_database_path),
            "--image_path", str(new_images_path),
            "--image_list_path", str(temp_image_list)
        ])

        # Step 2: Match new images against existing model
        print("Matching new images against existing model...")
        run_command([
            "colmap", "vocab_tree_matcher",
            "--database_path", str(merged_database_path),
            "--VocabTreeMatching.vocab_tree_path", "vocab_tree_flickr100K_words32K.bin",
            "--VocabTreeMatching.match_list_path", str(temp_image_list)
        ])

        # Step 3: Register new images into existing model
        print("Registering new images into the model...")
        run_command([
            "colmap", "image_registrator",
            "--database_path", str(merged_database_path),
            "--input_path", str(main_model_path),
            "--output_path", str(output_path)
        ])

        # Step 4: Bundle adjustment (optional but recommended)
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
        print(f"Merged model saved to: {output_path}")

    finally:
        # Cleanup temporary file
        if temp_image_list.exists():
            temp_image_list.unlink()

def main():
    try:
        register_new_images(
            main_model_path="dataset_main/sparse/0",    # Path to main model
            new_images_path="dataset_staging/images",    # Path directly to new images
            database_path="dataset_main/database.db",    # Path to main database
            output_path="dataset_merged/sparse/0"        # Output path for updated model
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 