import os
import subprocess
import shutil
from pathlib import Path

def run_command(command):
    """Run a command and check for errors"""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        raise e

def register_new_images(dataset_path="dataset", new_images_path="new_images", vocab_tree_path="vocab_tree_flickr100K_words32K.bin"):
    """
    Register new images into an existing COLMAP reconstruction.
    Following guide: https://colmap.github.io/faq.html#register-localize-new-images-into-an-existing-reconstruction
    """
    dataset_path = Path(dataset_path)
    new_images_path = Path(new_images_path)
    vocab_tree_path = Path(vocab_tree_path)
    
    # Check paths exist
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset path {dataset_path} not found!")
    if not new_images_path.exists():
        raise FileNotFoundError(f"New images path {new_images_path} not found!")
    if not vocab_tree_path.exists():
        raise FileNotFoundError(f"Vocabulary tree file not found at {vocab_tree_path}! Download it from COLMAP website.")
        
    database_path = dataset_path / "database.db"
    sparse_path = dataset_path / "sparse"
    existing_model_path = sparse_path / "0"  # Using first reconstruction
    images_path = dataset_path / "images"
    
    # Create images directory if it doesn't exist
    images_path.mkdir(exist_ok=True)
    
    # First, copy new images to the dataset/images folder
    print("Copying new images to dataset folder...")
    for img_path in new_images_path.glob("*"):
        if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            dest_path = images_path / img_path.name
            if not dest_path.exists():  # Only copy if doesn't exist
                shutil.copy2(img_path, dest_path)
                print(f"Copied {img_path.name} to dataset/images/")

    # Create image list file containing only new images
    image_list_path = dataset_path / "new_image_list.txt"
    with open(image_list_path, "w") as f:
        for img_path in new_images_path.glob("*"):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                f.write(f"{img_path.name}\n")

    print("Starting registration of new images...")

    # Step 1: Extract features for ONLY NEW images (using image_list_path)
    print("Step 1: Extracting features for new images...")
    run_command([
        "colmap", "feature_extractor",
        "--database_path", str(database_path),
        "--image_path", str(images_path),
        "--image_list_path", str(image_list_path)  # Only process new images
    ])

    # Step 2: Match new images against existing reconstruction using vocab tree
    print("Step 2: Matching features using vocabulary tree...")
    run_command([
        "colmap", "vocab_tree_matcher",
        "--database_path", str(database_path),
        "--VocabTreeMatching.vocab_tree_path", str(vocab_tree_path),
        "--VocabTreeMatching.match_list_path", str(image_list_path)
    ])

    # Step 3: Register new images into the existing model
    print("Step 3: Registering new images...")
    output_path = sparse_path / "registered"
    output_path.mkdir(exist_ok=True)
    
    run_command([
        "colmap", "image_registrator",
        "--database_path", str(database_path),
        "--input_path", str(existing_model_path),
        "--output_path", str(output_path)
    ])

    # Step 4: Bundle adjustment to refine the model
    print("Step 4: Running bundle adjustment...")
    final_path = sparse_path / "final"
    final_path.mkdir(exist_ok=True)
    
    run_command([
        "colmap", "bundle_adjuster",
        "--input_path", str(output_path),
        "--output_path", str(final_path)
    ])

    # Step 5: Convert the final model to TXT format
    print("Step 5: Converting model to TXT format...")
    run_command([
        "colmap", "model_converter",
        "--input_path", str(final_path),
        "--output_path", str(sparse_path),
        "--output_type", "TXT"
    ])

    # Cleanup
    image_list_path.unlink()
    
    print("\nRegistration completed successfully!")
    print(f"Final model saved in: {final_path}")
    print("\nNote: You'll need to re-run dense reconstruction if needed, as the model coordinate frame may have changed.")
    print("\nIMPORTANT: Make sure to download the vocabulary tree file (vocab_tree_flickr100k.bin) from the COLMAP website")

if __name__ == "__main__":
    try:
        register_new_images()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 