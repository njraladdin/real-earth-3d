from pathlib import Path
from filter_images import filter_images

def main():
    try:
        # Filter expansion images
        print("Filtering expansion images...")
        filter_images(input_folder="expansion_images")
        print("expansion image filtering complete!")
        
    except Exception as e:
        import traceback
        print(f"Error occurred during filtering: {e}")
        print(traceback.format_exc())
        exit(1)

if __name__ == "__main__":
    main()

 