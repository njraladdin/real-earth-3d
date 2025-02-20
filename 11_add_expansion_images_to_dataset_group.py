import os
from add_images_to_group import create_new_image_group

def main():
    try:
        # Source images from expansion_images_filtered
        source_images_path = "expansion_images_filtered"
        if not os.path.exists(source_images_path):
            raise Exception(f"Source images path not found: {source_images_path}")
            
        # Add images to a new group in the main dataset
        dataset_path = "dataset_main"
        if not os.path.exists(dataset_path):
            raise Exception(f"Dataset path not found: {dataset_path}")
            
        # Create new group with these images
        group_number = create_new_image_group(
            dataset_path=dataset_path, 
            clear_previous=False,
            source_images_path=source_images_path
        )
        print(f"Successfully created new image group {group_number}")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 