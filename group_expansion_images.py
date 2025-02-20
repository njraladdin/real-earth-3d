from pathlib import Path
from group_images import group_images_by_content

def main():
    # Define paths
    base_path = Path(".")
    input_path = base_path / "expansion_images"
    output_path = base_path / "expansion_images_grouped"
    
    # Check if input directory exists
    if not input_path.exists():
        print(f"Error: Input directory not found: {input_path}")
        exit(1)
    
    try:
        # Group the images using the existing function
        print(f"Grouping images from {input_path}")
        print(f"Results will be saved to {output_path}")
        
        grouped_images = group_images_by_content(
            input_path=input_path,
            output_path=output_path,
            n_clusters=4,  # You can adjust this number based on your needs
            min_group_size=2  # Minimum number of images per group
        )
        
        if grouped_images:
            print("\nGrouping completed successfully!")
            
    except Exception as e:
        import traceback
        print(f"Error occurred while grouping images: {e}")
        print(traceback.format_exc())
        exit(1)

if __name__ == "__main__":
    main() 