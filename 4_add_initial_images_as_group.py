import os
from add_images_to_group import create_new_image_group

def add_initial_images_as_group():
    try:
        # Add images to a new group in the main dataset
        dataset_path = "dataset_main"
        if not os.path.exists(dataset_path):
            raise Exception(f"Dataset path not found: {dataset_path}")

        # Create new group with these images
        group_number = create_new_image_group(
            dataset_path=dataset_path, 
            clear_previous=False,
            source_images_path="initial_images_filtered"
        )
        print(f"Successfully created new image group {group_number}")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    add_initial_images_as_group()


