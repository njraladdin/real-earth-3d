from run_colmap import run_colmap_pipeline

def main():
    try:
        run_colmap_pipeline(
            dataset_path="dataset_main",
            input_images_path="initial_images_filtered",
            cleanup_existing=True  # Don't clear existing files for initial run
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()  