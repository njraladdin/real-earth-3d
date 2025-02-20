import os
import shutil
from pathlib import Path
from match_images_with_group import ImageMatcher

def match_expansion_images_with_a_group():
    # Define paths
    expansion_dir = Path("expansion_images_filtered")
    dataset_dir = Path("dataset_main")
    output_dir = Path("expansion_images_matched")
    grouped_images_dir = dataset_dir / "grouped_images"

    # Use ImageMatcher to process and copy images
    print("Matching images with existing groups...")
    try:
        matcher = ImageMatcher(
            source_path=expansion_dir,
            groups_path=grouped_images_dir
        )
        
        matching_group = matcher.match_images_with_group(output_dir)
        
        if matching_group:
            print(f"Successfully matched and copied images with group: {matching_group}")
        else:
            print("No matching group found. Process aborted.")
            if output_dir.exists():
                shutil.rmtree(output_dir)
    except Exception as e:
        print(f"Error during matching process: {e}")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        return

if __name__ == "__main__":
    match_expansion_images_with_a_group()
