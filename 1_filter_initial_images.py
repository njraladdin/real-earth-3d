from pathlib import Path
from filter_images import filter_images

def main():
    try:
        # Filter initial images
        print("Filtering initial images...")
        filter_images(input_folder="initial_images")
        print("Initial image filtering complete!")
        
    except Exception as e:
        import traceback
        print(f"Error occurred during filtering: {e}")
        print(traceback.format_exc())
        exit(1)

if __name__ == "__main__":
    main()
#
