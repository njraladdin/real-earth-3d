from run_colmap import run_colmap_pipeline

def main():
    try:
        run_colmap_pipeline(
            dataset_path="dataset_staging",
            input_images_path="expansion_images_matched",
            cleanup_existing=True  # Clear existing files for expansion run
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 