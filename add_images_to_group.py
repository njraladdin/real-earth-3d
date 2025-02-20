import os
import shutil
from glob import glob

def create_new_image_group(dataset_path, clear_previous=False, source_images_path=None):
    """Create a new group and copy processed images into it.
    
    Args:
        dataset_path (str): Path to the dataset directory containing 'images' folder
        clear_previous (bool): If True, removes all existing groups before creating new one.
                             If False, creates a new group with next available number.
        source_images_path (str, optional): Path to source images to copy. If None, uses dataset_path/images
        
    Returns:
        int: The group number that was created
    """
    # Define paths
    images_path = source_images_path if source_images_path else os.path.join(dataset_path, 'images')
    grouped_images_path = os.path.join(dataset_path, 'grouped_images')
    
    if not os.path.exists(images_path):
        raise Exception(f"Source images path not found: {images_path}")
    
    # Create grouped_images directory if it doesn't exist
    if not os.path.exists(grouped_images_path):
        os.makedirs(grouped_images_path)
    elif clear_previous:
        shutil.rmtree(grouped_images_path)
        os.makedirs(grouped_images_path)
    
    # Determine next group number
    existing_groups = [int(d) for d in os.listdir(grouped_images_path) 
                      if os.path.isdir(os.path.join(grouped_images_path, d)) and d.isdigit()]
    new_group_number = 0 if not existing_groups else max(existing_groups) + 1
    
    # Create new group
    new_group_path = os.path.join(grouped_images_path, str(new_group_number))
    os.makedirs(new_group_path)
    
    # Copy all images from images directory to the new group
    for image_file in glob(os.path.join(images_path, '*')):
        if os.path.isfile(image_file):
            shutil.copy2(image_file, new_group_path)
    
    return new_group_number 